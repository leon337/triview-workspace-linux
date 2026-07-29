"""Live-workspace browser backend with hidden startup and input routing."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from triview_workspace.engines.browser import (
    BrowserEngine,
    BrowserLaunchError,
    BrowserLaunchRequest,
    BrowserSession,
)
from triview_workspace.engines.browser_embedded import (
    STAGING_COORDINATE,
    terminate_process_group,
)
from triview_workspace.engines.browser_final_client import BrowserWindowIdentity
from triview_workspace.engines.browser_final_client_xfwm4 import (
    Xfwm4FinalClientX11BraveBrowserBackend,
)
from triview_workspace.runtime_observability import record_runtime_event


NO_FLASH_BROWSER_BACKEND_NAME = "NoFlashXfwm4FinalClientX11BraveBrowserBackend"
_PROFILE_IGNORE = shutil.ignore_patterns(
    "SingletonCookie",
    "SingletonLock",
    "SingletonSocket",
    ".org.chromium.*",
)


def safe_runtime_token(value: str) -> str:
    """Return a filesystem and WM_CLASS-safe token for one runtime identity."""

    token = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return token or "panel"


def build_no_flash_browser_command(
    browser: str,
    request: BrowserLaunchRequest,
) -> tuple[str, ...]:
    """Launch Chromium minimized and outside the visible work area."""

    return (
        browser,
        f"--app={request.url}",
        f"--user-data-dir={request.profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--ozone-platform=x11",
        "--start-minimized",
        f"--class={request.window_class}",
        f"--name={request.window_class}",
        f"--window-position={STAGING_COORDINATE},{STAGING_COORDINATE}",
        "--window-size=800,600",
    )


def is_final_browser_candidate(
    identity: BrowserWindowIdentity,
    *,
    expected_class: str,
    expected_process_group: int,
) -> bool:
    """Accept a titled final client even while it is still hidden/minimized."""

    title = identity.title.strip()
    folded_title = title.casefold()
    folded_class = expected_class.casefold()
    return bool(
        identity.window_class.casefold() == folded_class
        and identity.process_group == int(expected_process_group)
        and identity.parent is not None
        and title
        and folded_title != folded_class
        and not folded_title.startswith("triview-")
    )


class NoFlashXfwm4FinalClientX11BraveBrowserBackend(
    Xfwm4FinalClientX11BraveBrowserBackend
):
    """Discover the final client while hidden, then expose it only inside the host."""

    def __init__(
        self,
        launch_timeout: float = 15.0,
        poll_interval: float = 0.02,
        reparent_attempts: int = 8,
        stable_parent_checks: int = 5,
        final_window_checks: int = 3,
    ) -> None:
        super().__init__(
            launch_timeout=launch_timeout,
            poll_interval=poll_interval,
            reparent_attempts=reparent_attempts,
            stable_parent_checks=stable_parent_checks,
            final_window_checks=final_window_checks,
        )
        self._last_pointer_focused_window: str | None = None

    def launch(
        self,
        request: BrowserLaunchRequest,
        parent_window_id: int,
    ) -> BrowserSession:
        report = self.availability()
        record_runtime_event(
            "browser_launch_requested",
            backend=NO_FLASH_BROWSER_BACKEND_NAME,
            panel_id=request.panel_id,
            url=request.url,
            profile_dir=str(request.profile_dir),
            window_class=request.window_class,
            host_window_id=int(parent_window_id),
            hidden_start=True,
        )
        if not report.available:
            raise BrowserLaunchError(report.reason)
        assert report.browser_command is not None
        assert report.xdotool_command is not None
        xwininfo = shutil.which("xwininfo")
        assert xwininfo is not None

        request.profile_dir.mkdir(parents=True, exist_ok=True)
        known_window_ids = set(
            self._search_matching_windows(
                report.xdotool_command,
                request.window_class,
                only_visible=False,
            )
        )
        command = build_no_flash_browser_command(report.browser_command, request)
        process = subprocess.Popen(  # noqa: S603
            list(command),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        record_runtime_event(
            "browser_process_started",
            panel_id=request.panel_id,
            browser_pid=process.pid,
            command=list(command),
            hidden_start=True,
        )

        window_id: str | None = None
        try:
            window_id = self._wait_for_unique_window(
                report.xdotool_command,
                request.window_class,
                process,
                known_window_ids,
            )
            visible_before_staging = self._window_is_viewable(xwininfo, window_id)
            parent_before_staging = self._window_parent(xwininfo, window_id)
            self._hide_and_stage_window(report.xdotool_command, window_id)
            record_runtime_event(
                "browser_window_hidden_staging",
                panel_id=request.panel_id,
                browser_pid=process.pid,
                browser_window_id=window_id,
                parent_before=parent_before_staging,
                visible_before=visible_before_staging,
                staging_coordinate=STAGING_COORDINATE,
            )
            self._wait_for_first_managed_map(
                report.xdotool_command,
                xwininfo,
                window_id,
                process,
                request.panel_id,
            )
            if not self._reparent_after_first_map(
                report.xdotool_command,
                xwininfo,
                window_id,
                parent_window_id,
                request.panel_id,
            ):
                raise BrowserLaunchError(
                    "O navegador foi mapeado em staging, mas o Xfwm4 não manteve "
                    "a janela dentro do host do painel."
                )
        except Exception as exc:
            record_runtime_event(
                "browser_launch_failed",
                panel_id=request.panel_id,
                browser_pid=process.pid,
                browser_window_id=window_id,
                host_window_id=int(parent_window_id),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            if window_id is not None:
                try:
                    self._run_xdotool(
                        report.xdotool_command,
                        "windowclose",
                        window_id,
                    )
                except BrowserLaunchError:
                    pass
            terminate_process_group(process)
            raise

        session = BrowserSession(
            panel_id=request.panel_id,
            url=request.url,
            process=process,
            window_id=window_id,
            embedded=True,
        )
        self._close_stale_placeholders(request, session)
        record_runtime_event(
            "browser_launch_embedded",
            panel_id=request.panel_id,
            browser_pid=process.pid,
            browser_window_id=window_id,
            host_window_id=int(parent_window_id),
            parent_after=self._window_parent(xwininfo, window_id),
            visible_after=self._window_is_viewable(xwininfo, window_id),
            embedded=True,
            hidden_start=True,
        )
        return session

    def _wait_for_unique_window(
        self,
        xdotool: str,
        window_class: str,
        process: subprocess.Popen[bytes],
        known_window_ids: set[str],
    ) -> str:
        """Select the stable final client without requiring it to be viewable."""

        xwininfo = shutil.which("xwininfo")
        if xwininfo is None:
            raise BrowserLaunchError(
                "O utilitário xwininfo não está disponível para selecionar a janela final."
            )

        deadline = time.monotonic() + self._launch_timeout
        stability: dict[str, int] = {}
        process_exit_seen_at: float | None = None
        last_observation: dict[str, tuple[object, ...]] = {}

        while time.monotonic() < deadline:
            candidates = self._search_matching_windows(
                xdotool,
                window_class,
                only_visible=False,
            )
            current_new_ids = {
                window_id for window_id in candidates if window_id not in known_window_ids
            }
            for window_id in candidates:
                if window_id in known_window_ids:
                    continue
                identity = self._window_identity(xdotool, xwininfo, window_id)
                eligible = is_final_browser_candidate(
                    identity,
                    expected_class=window_class,
                    expected_process_group=process.pid,
                )
                signature = (
                    identity.title,
                    identity.window_class,
                    identity.pid,
                    identity.process_group,
                    identity.parent,
                    identity.viewable,
                    eligible,
                )
                if last_observation.get(window_id) != signature:
                    record_runtime_event(
                        "browser_window_candidate_observed",
                        browser_window_id=window_id,
                        expected_window_class=window_class,
                        browser_process_group=process.pid,
                        title=identity.title,
                        window_class=identity.window_class,
                        window_pid=identity.pid,
                        window_process_group=identity.process_group,
                        parent=identity.parent,
                        viewable=identity.viewable,
                        eligible_final_client=eligible,
                        hidden_candidate_allowed=True,
                    )
                    last_observation[window_id] = signature
                if eligible:
                    stability[window_id] = stability.get(window_id, 0) + 1
                    if stability[window_id] >= self._final_window_checks:
                        record_runtime_event(
                            "browser_final_client_selected",
                            browser_window_id=window_id,
                            expected_window_class=window_class,
                            title=identity.title,
                            window_pid=identity.pid,
                            window_process_group=identity.process_group,
                            parent=identity.parent,
                            viewable=identity.viewable,
                            stable_checks=stability[window_id],
                            selected_while_hidden=not identity.viewable,
                        )
                        return window_id
                else:
                    stability[window_id] = 0

            for stale_id in set(stability) - current_new_ids:
                stability.pop(stale_id, None)

            if process.poll() is not None:
                if process_exit_seen_at is None:
                    process_exit_seen_at = time.monotonic()
                elif time.monotonic() - process_exit_seen_at >= min(
                    3.0,
                    self._launch_timeout,
                ):
                    break
            time.sleep(self._poll_interval)

        raise BrowserLaunchError(
            "O Brave iniciou oculto, mas nenhuma janela final titulada foi identificada."
        )

    def _hide_and_stage_window(self, xdotool: str, window_id: str) -> None:
        """Unmap before moving so an already-created window cannot remain visible."""

        try:
            self._run_xdotool(xdotool, "windowunmap", window_id)
        except BrowserLaunchError:
            pass
        self._run_xdotool(
            xdotool,
            "windowmove",
            window_id,
            str(STAGING_COORDINATE),
            str(STAGING_COORDINATE),
        )

    def focus_session_under_pointer(
        self,
        sessions: dict[str, BrowserSession],
    ) -> str | None:
        """Focus the embedded browser currently below the system pointer."""

        xdotool = self._xdotool_command()
        xwininfo = shutil.which("xwininfo")
        if xdotool is None or xwininfo is None:
            return None
        try:
            result = subprocess.run(  # noqa: S603
                [xdotool, "getmouselocation", "--shell"],
                capture_output=True,
                text=True,
                check=False,
                timeout=1,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        pointer_window = ""
        for line in result.stdout.splitlines():
            if line.startswith("WINDOW="):
                pointer_window = line.split("=", 1)[1].strip()
                break
        if not pointer_window:
            return None

        for runtime_id, session in sessions.items():
            if not session.window_id:
                continue
            if not self._is_same_or_descendant(
                xwininfo, pointer_window, session.window_id
            ):
                continue
            if self._last_pointer_focused_window != session.window_id:
                if not self.focus(session):
                    return None
                self._last_pointer_focused_window = session.window_id
                record_runtime_event(
                    "browser_pointer_focus_applied",
                    runtime_id=runtime_id,
                    browser_window_id=session.window_id,
                    pointer_window_id=pointer_window,
                )
            return runtime_id
        self._last_pointer_focused_window = None
        return None

    def _is_same_or_descendant(
        self,
        xwininfo: str,
        candidate_window: str,
        ancestor_window: str,
    ) -> bool:
        current = candidate_window
        normalized_ancestor = str(int(ancestor_window, 0)) if ancestor_window else ""
        for _depth in range(12):
            try:
                normalized_current = str(int(current, 0))
            except ValueError:
                return False
            if normalized_current == normalized_ancestor:
                return True
            parent = self._window_parent(xwininfo, current)
            if parent is None or parent <= 0 or str(parent) == normalized_current:
                return False
            current = str(parent)
        return False

    def focus(self, session: BrowserSession) -> bool:
        """Focus one embedded browser window without activating an external shell."""

        if not session.window_id:
            return False
        xdotool = self._xdotool_command()
        if xdotool is None:
            return False
        try:
            self._run_xdotool(xdotool, "windowfocus", session.window_id)
        except BrowserLaunchError:
            return False
        return True

    def scroll(self, session: BrowserSession, steps: int) -> bool:
        """Deliver wheel steps directly to the embedded X11 child window."""

        if not session.window_id or steps == 0:
            return False
        xdotool = self._xdotool_command()
        if xdotool is None:
            return False
        button = "4" if steps > 0 else "5"
        repeat = min(12, max(1, abs(int(steps))))
        try:
            self._run_xdotool(
                xdotool,
                "click",
                "--window",
                session.window_id,
                "--repeat",
                str(repeat),
                button,
            )
        except BrowserLaunchError:
            return False
        return True


class LiveBrowserEngine(BrowserEngine):
    """Browser engine with workspace-scoped profiles and observable input helpers."""

    def open(
        self,
        panel_id: str,
        target: str,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> BrowserSession:
        self._migrate_legacy_profile(panel_id)
        return super().open(panel_id, target, parent_window_id, width, height)

    def session(self, panel_id: str) -> BrowserSession | None:
        with self._lock:
            return self._sessions.get(panel_id)

    def focus(self, panel_id: str) -> bool:
        session = self.session(panel_id)
        if session is None:
            return False
        focus = getattr(self._backend, "focus", None)
        return bool(focus(session)) if callable(focus) else False

    def scroll(self, panel_id: str, steps: int) -> bool:
        session = self.session(panel_id)
        if session is None:
            return False
        scroll = getattr(self._backend, "scroll", None)
        return bool(scroll(session, steps)) if callable(scroll) else False

    def focus_under_pointer(self) -> str | None:
        backend_method = getattr(self._backend, "focus_session_under_pointer", None)
        if not callable(backend_method):
            return None
        with self._lock:
            sessions = dict(self._sessions)
        return backend_method(sessions)

    def _migrate_legacy_profile(self, panel_id: str) -> None:
        if "::" not in panel_id:
            return
        _workspace_id, local_panel_id = panel_id.split("::", 1)
        target = self._profile_root / safe_runtime_token(panel_id)
        legacy = self._profile_root / safe_runtime_token(local_panel_id)
        if target.exists() or not legacy.is_dir():
            return
        try:
            shutil.copytree(legacy, target, ignore=_PROFILE_IGNORE)
        except OSError as exc:
            record_runtime_event(
                "browser_profile_namespace_migration_failed",
                runtime_panel_id=panel_id,
                legacy_profile=str(legacy),
                target_profile=str(target),
                error=str(exc),
            )
            return
        record_runtime_event(
            "browser_profile_namespace_migrated",
            runtime_panel_id=panel_id,
            legacy_profile=str(legacy),
            target_profile=str(target),
        )


__all__ = [
    "LiveBrowserEngine",
    "NO_FLASH_BROWSER_BACKEND_NAME",
    "NoFlashXfwm4FinalClientX11BraveBrowserBackend",
    "build_no_flash_browser_command",
    "is_final_browser_candidate",
    "safe_runtime_token",
]
