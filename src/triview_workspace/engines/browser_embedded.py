"""Atomic X11 browser embedding for the RC4 candidate."""

from __future__ import annotations

import logging
import os
import re
import shutil
import signal
import subprocess
import time

from triview_workspace.engines.browser import (
    BrowserBackendAvailability,
    BrowserLaunchError,
    BrowserLaunchRequest,
    BrowserSession,
    X11BraveBrowserBackend,
)
from triview_workspace.engines.panel_runtime import parse_parent_window_id

LOGGER = logging.getLogger(__name__)

STAGING_COORDINATE = -32_000
BROWSER_POLL_INTERVAL = 0.02
BROWSER_REPARENT_ATTEMPTS = 8
BROWSER_STABLE_PARENT_CHECKS = 5


def exact_x11_pattern(value: str) -> str:
    """Return an anchored regex safe for xdotool's regex-based search."""

    return rf"^{re.escape(value)}$"


def build_staged_browser_command(
    browser: str,
    request: BrowserLaunchRequest,
) -> tuple[str, ...]:
    """Launch a Chromium app window outside the visible desktop work area."""

    return (
        browser,
        f"--app={request.url}",
        f"--user-data-dir={request.profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--class={request.window_class}",
        f"--name={request.window_class}",
        f"--window-position={STAGING_COORDINATE},{STAGING_COORDINATE}",
        "--window-size=800,600",
    )


def terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    """Terminate the complete detached process group, including forked children."""

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    except PermissionError:
        if process.poll() is None:
            process.terminate()

    if process.poll() is None:
        try:
            process.wait(timeout=1.5)
        except subprocess.TimeoutExpired:
            pass

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except PermissionError:
        if process.poll() is None:
            process.kill()


class AtomicX11BraveBrowserBackend(X11BraveBrowserBackend):
    """Stage Chromium, let Muffin manage it once, then embed it permanently."""

    def __init__(
        self,
        launch_timeout: float = 15.0,
        poll_interval: float = BROWSER_POLL_INTERVAL,
        reparent_attempts: int = BROWSER_REPARENT_ATTEMPTS,
        stable_parent_checks: int = BROWSER_STABLE_PARENT_CHECKS,
    ) -> None:
        super().__init__(launch_timeout=launch_timeout)
        self._poll_interval = max(0.01, float(poll_interval))
        self._reparent_attempts = max(1, int(reparent_attempts))
        self._stable_parent_checks = max(2, int(stable_parent_checks))

    def availability(self) -> BrowserBackendAvailability:
        report = super().availability()
        if not report.available:
            return report
        if shutil.which("xwininfo") is None:
            return BrowserBackendAvailability(
                False,
                "O utilitário xwininfo é necessário para confirmar a incorporação X11.",
                browser_command=report.browser_command,
                xdotool_command=report.xdotool_command,
            )
        return BrowserBackendAvailability(
            True,
            "Backend X11 pronto para incorporar o navegador após o primeiro map gerenciado.",
            browser_command=report.browser_command,
            xdotool_command=report.xdotool_command,
        )

    def launch(
        self,
        request: BrowserLaunchRequest,
        parent_window_id: int,
    ) -> BrowserSession:
        report = self.availability()
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
        command = build_staged_browser_command(report.browser_command, request)
        process = subprocess.Popen(  # noqa: S603
            list(command),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        window_id: str | None = None

        try:
            window_id = self._wait_for_unique_window(
                report.xdotool_command,
                request.window_class,
                process,
                known_window_ids,
            )
            self._stage_window(report.xdotool_command, window_id)
            self._wait_for_first_managed_map(
                report.xdotool_command,
                xwininfo,
                window_id,
                process,
            )
            if not self._reparent_after_first_map(
                report.xdotool_command,
                xwininfo,
                window_id,
                parent_window_id,
                request.panel_id,
            ):
                raise BrowserLaunchError(
                    "O navegador foi mapeado, mas o window manager não manteve "
                    "a janela dentro do host X11 do painel."
                )
        except Exception:
            if window_id is not None:
                try:
                    self._run_xdotool(report.xdotool_command, "windowclose", window_id)
                except BrowserLaunchError:
                    pass
            terminate_process_group(process)
            raise

        return BrowserSession(
            panel_id=request.panel_id,
            url=request.url,
            process=process,
            window_id=window_id,
            embedded=True,
        )

    def close(self, session: BrowserSession) -> None:
        xdotool = self._xdotool_command()
        if session.window_id and xdotool:
            try:
                self._run_xdotool(xdotool, "windowclose", session.window_id)
            except BrowserLaunchError:
                pass
        if session.process is not None:
            terminate_process_group(session.process)

    def _wait_for_unique_window(
        self,
        xdotool: str,
        window_class: str,
        process: subprocess.Popen[bytes],
        known_window_ids: set[str],
    ) -> str:
        deadline = time.monotonic() + self._launch_timeout
        process_exit_seen_at: float | None = None

        while time.monotonic() < deadline:
            candidates = self._search_matching_windows(
                xdotool,
                window_class,
                only_visible=False,
            )
            new_candidates = [
                window_id for window_id in candidates if window_id not in known_window_ids
            ]
            if new_candidates:
                return new_candidates[-1]

            if process.poll() is not None:
                if process_exit_seen_at is None:
                    process_exit_seen_at = time.monotonic()
                elif time.monotonic() - process_exit_seen_at >= 1.0:
                    break
            time.sleep(self._poll_interval)

        raise BrowserLaunchError(
            "A janela X11 exclusiva do navegador não foi localizada para incorporação."
        )

    @staticmethod
    def _search_matching_windows(
        xdotool: str,
        value: str,
        *,
        only_visible: bool,
    ) -> list[str]:
        pattern = exact_x11_pattern(value)
        ordered: list[str] = []
        seen: set[str] = set()
        for selector in ("--class", "--classname", "--name"):
            arguments = [xdotool, "search"]
            if only_visible:
                arguments.append("--onlyvisible")
            arguments.extend((selector, pattern))
            result = subprocess.run(  # noqa: S603
                arguments,
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            if result.returncode not in (0, 1):
                continue
            for window_id in result.stdout.splitlines():
                normalized = window_id.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    ordered.append(normalized)
        return ordered

    def _stage_window(self, xdotool: str, window_id: str) -> None:
        """Keep the first managed map outside the visible work area."""

        self._run_xdotool(
            xdotool,
            "windowmove",
            window_id,
            str(STAGING_COORDINATE),
            str(STAGING_COORDINATE),
        )

    def _wait_for_first_managed_map(
        self,
        xdotool: str,
        xwininfo: str,
        window_id: str,
        process: subprocess.Popen[bytes],
    ) -> None:
        """Allow Muffin to complete its initial management before reparenting."""

        try:
            self._run_xdotool(xdotool, "windowmap", window_id)
        except BrowserLaunchError:
            LOGGER.debug("Chromium window was already mapped before staging.")

        deadline = time.monotonic() + min(4.0, self._launch_timeout)
        while time.monotonic() < deadline:
            if self._window_is_viewable(xwininfo, window_id):
                return
            if process.poll() is not None:
                break
            time.sleep(self._poll_interval)
        raise BrowserLaunchError(
            "A janela Chromium não concluiu o primeiro map gerenciado pelo desktop."
        )

    def _reparent_after_first_map(
        self,
        xdotool: str,
        xwininfo: str,
        window_id: str,
        parent_window_id: int,
        panel_id: str,
    ) -> bool:
        """Reparent after mapping and retry if the window manager reclaims Chromium."""

        for attempt in range(1, self._reparent_attempts + 1):
            try:
                self._run_xdotool(
                    xdotool,
                    "windowmove",
                    window_id,
                    str(STAGING_COORDINATE),
                    str(STAGING_COORDINATE),
                )
                try:
                    self._run_xdotool(xdotool, "windowunmap", window_id)
                except BrowserLaunchError:
                    pass
                self._run_xdotool(
                    xdotool,
                    "windowreparent",
                    window_id,
                    str(parent_window_id),
                )
                self._run_xdotool(xdotool, "windowmove", window_id, "0", "0")
                self._run_xdotool(xdotool, "windowmap", window_id)
            except BrowserLaunchError:
                LOGGER.warning(
                    "Browser reparent transaction %s/%s failed for panel %s.",
                    attempt,
                    self._reparent_attempts,
                    panel_id,
                    exc_info=True,
                )
            else:
                if self._confirm_mapped_parent(
                    xwininfo,
                    window_id,
                    parent_window_id,
                ):
                    return True
                LOGGER.warning(
                    "Muffin reclaimed browser window %s after attempt %s/%s for panel %s.",
                    window_id,
                    attempt,
                    self._reparent_attempts,
                    panel_id,
                )
            time.sleep(max(0.05, self._poll_interval))
        return False

    @staticmethod
    def _window_is_viewable(xwininfo: str, window_id: str) -> bool:
        result = subprocess.run(  # noqa: S603
            [xwininfo, "-id", window_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        if result.returncode != 0:
            return False
        return "map state: isviewable" in result.stdout.casefold()

    def _confirm_mapped_parent(
        self,
        xwininfo: str,
        window_id: str,
        expected_parent: int,
    ) -> bool:
        matches = 0
        max_checks = self._stable_parent_checks * 4 + 8
        for _attempt in range(max_checks):
            result = subprocess.run(  # noqa: S603
                [xwininfo, "-id", window_id, "-tree"],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
            parent = parse_parent_window_id(result.stdout) if result.returncode == 0 else None
            if parent == int(expected_parent) and self._window_is_viewable(
                xwininfo,
                window_id,
            ):
                matches += 1
                if matches >= self._stable_parent_checks:
                    return True
            else:
                matches = 0
            time.sleep(self._poll_interval)
        return False


__all__ = [
    "AtomicX11BraveBrowserBackend",
    "BROWSER_POLL_INTERVAL",
    "BROWSER_REPARENT_ATTEMPTS",
    "BROWSER_STABLE_PARENT_CHECKS",
    "STAGING_COORDINATE",
    "build_staged_browser_command",
    "exact_x11_pattern",
    "terminate_process_group",
]
