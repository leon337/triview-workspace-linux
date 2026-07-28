"""Select the final Chromium app client before X11 embedding.

The XFCE/Xfwm4 diagnostic showed that Brave can expose more than one X11
window with the requested TriView class.  The first one is a transient or
placeholder client whose title is empty or equal to the requested class.  The
real application window appears shortly afterwards with the page title and a
PID in the browser process group.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass

from triview_workspace.engines.browser import (
    BrowserLaunchError,
    BrowserLaunchRequest,
    BrowserSession,
)
from triview_workspace.engines.browser_embedded import AtomicX11BraveBrowserBackend
from triview_workspace.runtime_observability import record_runtime_event


@dataclass(frozen=True, slots=True)
class BrowserWindowIdentity:
    """Observed X11 identity used to distinguish placeholders from the app."""

    window_id: str
    title: str
    window_class: str
    pid: int | None
    process_group: int | None
    parent: int | None
    viewable: bool


def is_final_browser_client(
    identity: BrowserWindowIdentity,
    *,
    expected_class: str,
    expected_process_group: int,
) -> bool:
    """Return whether an observed window is the final managed browser client."""

    title = identity.title.strip()
    folded_title = title.casefold()
    folded_class = expected_class.casefold()
    return bool(
        identity.window_class.casefold() == folded_class
        and identity.process_group == int(expected_process_group)
        and identity.parent is not None
        and identity.viewable
        and title
        and folded_title != folded_class
        and not folded_title.startswith("triview-")
    )


class FinalClientX11BraveBrowserBackend(AtomicX11BraveBrowserBackend):
    """Embed the final Chromium app client instead of its startup placeholder."""

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
        )
        self._final_window_checks = max(2, int(final_window_checks))

    def launch(
        self,
        request: BrowserLaunchRequest,
        parent_window_id: int,
    ) -> BrowserSession:
        session = super().launch(request, parent_window_id)
        self._close_stale_placeholders(request, session)
        return session

    def _wait_for_unique_window(
        self,
        xdotool: str,
        window_class: str,
        process: subprocess.Popen[bytes],
        known_window_ids: set[str],
    ) -> str:
        """Wait for a stable, titled client from the spawned browser process group."""

        xwininfo = shutil.which("xwininfo")
        if xwininfo is None:
            raise BrowserLaunchError(
                "O utilitário xwininfo não está disponível para selecionar a janela final."
            )

        deadline = time.monotonic() + self._launch_timeout
        process_exit_seen_at: float | None = None
        stability: dict[str, int] = {}
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
                eligible = is_final_browser_client(
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
                            stable_checks=stability[window_id],
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
            "O Brave abriu, mas nenhuma janela final titulada do processo lançado "
            "foi identificada. Janelas intermediárias foram ignoradas."
        )

    @staticmethod
    def _search_matching_windows(
        xdotool: str,
        value: str,
        *,
        only_visible: bool,
    ) -> list[str]:
        """Search only the exact WM_CLASS, avoiding title and instance collisions."""

        pattern = f"^{value.replace('\\', '\\\\').replace('.', '\\.').replace('-', '\\-')}$"
        arguments = [xdotool, "search"]
        if only_visible:
            arguments.append("--onlyvisible")
        arguments.extend(("--class", pattern))
        result = subprocess.run(  # noqa: S603
            arguments,
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode not in (0, 1):
            return []
        ordered: list[str] = []
        seen: set[str] = set()
        for line in result.stdout.splitlines():
            window_id = line.strip()
            if window_id and window_id not in seen:
                seen.add(window_id)
                ordered.append(window_id)
        return ordered

    def _window_identity(
        self,
        xdotool: str,
        xwininfo: str,
        window_id: str,
    ) -> BrowserWindowIdentity:
        title = self._xdotool_value(xdotool, "getwindowname", window_id)
        window_class = self._xdotool_value(xdotool, "getwindowclassname", window_id)
        raw_pid = self._xdotool_value(xdotool, "getwindowpid", window_id)
        try:
            pid = int(raw_pid)
        except (TypeError, ValueError):
            pid = None

        process_group: int | None = None
        if pid is not None:
            try:
                process_group = os.getpgid(pid)
            except (ProcessLookupError, PermissionError):
                process_group = None

        return BrowserWindowIdentity(
            window_id=window_id,
            title=title,
            window_class=window_class,
            pid=pid,
            process_group=process_group,
            parent=self._window_parent(xwininfo, window_id),
            viewable=self._window_is_viewable(xwininfo, window_id),
        )

    @staticmethod
    def _xdotool_value(xdotool: str, operation: str, window_id: str) -> str:
        result = subprocess.run(  # noqa: S603
            [xdotool, operation, window_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode != 0:
            return ""
        return result.stdout.strip()

    def _close_stale_placeholders(
        self,
        request: BrowserLaunchRequest,
        session: BrowserSession,
    ) -> None:
        if session.window_id is None or session.process is None:
            return
        xdotool = self._xdotool_command()
        xwininfo = shutil.which("xwininfo")
        if xdotool is None or xwininfo is None:
            return

        expected_group = session.process.pid
        for window_id in self._search_matching_windows(
            xdotool,
            request.window_class,
            only_visible=False,
        ):
            if window_id == session.window_id:
                continue
            identity = self._window_identity(xdotool, xwininfo, window_id)
            folded_title = identity.title.strip().casefold()
            placeholder = (
                identity.process_group == expected_group
                and (
                    not folded_title
                    or folded_title == request.window_class.casefold()
                    or folded_title.startswith("triview-")
                )
            )
            if not placeholder:
                continue
            try:
                self._run_xdotool(xdotool, "windowclose", window_id)
            except BrowserLaunchError as exc:
                record_runtime_event(
                    "browser_placeholder_close_failed",
                    panel_id=request.panel_id,
                    browser_window_id=window_id,
                    error=str(exc),
                )
            else:
                record_runtime_event(
                    "browser_placeholder_closed",
                    panel_id=request.panel_id,
                    browser_window_id=window_id,
                    title=identity.title,
                    window_pid=identity.pid,
                    window_process_group=identity.process_group,
                )


__all__ = [
    "BrowserWindowIdentity",
    "FinalClientX11BraveBrowserBackend",
    "is_final_browser_client",
]
