"""Embedded-first terminal runtime for the RC4 desktop candidate."""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

from triview_workspace.engines.panel_runtime import (
    PanelLaunchError,
    PanelRuntimeLaunchRequest,
    PanelRuntimeSession,
    X11PanelRuntimeBackend,
    resolve_command,
    safe_panel_token,
)
from triview_workspace.engines.runtime_controllers import TerminalRuntimeController
from triview_workspace.engines.terminal import (
    TerminalEngine,
    TerminalEngineError,
    X11TerminalBackend,
)

LOGGER = logging.getLogger(__name__)


class EmbeddedFirstX11PanelRuntimeBackend(X11PanelRuntimeBackend):
    """Discover and hide a terminal window before its first external map."""

    def __init__(self) -> None:
        super().__init__(
            launch_timeout=14.0,
            poll_interval=0.01,
            reparent_attempts=12,
            stable_parent_checks=2,
        )

    def _candidate_window_ids(
        self,
        xdotool: str,
        family_pids: set[int],
        hints: Sequence[str],
        known_window_ids: set[str],
    ) -> list[str]:
        """Search hidden and visible windows so reparenting can beat first exposure."""

        ordered: list[str] = []
        seen: set[str] = set()

        def add(window_ids: Sequence[str]) -> None:
            for window_id in window_ids:
                if window_id in known_window_ids or window_id in seen:
                    continue
                seen.add(window_id)
                ordered.append(window_id)

        for pid in sorted(family_pids):
            add(self._search_windows(xdotool, "--pid", str(pid), only_visible=False))

        hinted: list[str] = []
        for hint in hints:
            for selector in ("--class", "--classname", "--name"):
                hinted.extend(
                    self._search_windows(xdotool, selector, hint, only_visible=False)
                )

        family_hinted: list[str] = []
        unowned_hinted: list[str] = []
        for window_id in hinted:
            window_pid = self._window_pid(xdotool, window_id)
            if window_pid in family_pids:
                family_hinted.append(window_id)
            elif window_pid is None:
                unowned_hinted.append(window_id)

        add(family_hinted)
        if ordered:
            return ordered

        unique_unowned = list(dict.fromkeys(unowned_hinted))
        if len(unique_unowned) == 1:
            add(unique_unowned)
        elif len(unique_unowned) > 1:
            LOGGER.warning(
                "Ignoring %s ambiguous terminal windows without PID metadata.",
                len(unique_unowned),
            )
        return ordered

    def _wait_for_window(
        self,
        xdotool: str,
        xwininfo: str,
        process: subprocess.Popen[bytes],
        hints: Sequence[str],
        known_window_ids: set[str],
    ) -> str | None:
        deadline = time.monotonic() + self._launch_timeout
        normalized_hints = tuple(dict.fromkeys(hint.strip() for hint in hints if hint.strip()))
        observed_family_pids = {int(process.pid)}

        while time.monotonic() < deadline:
            observed_family_pids.update(self._process_family(process.pid))
            candidates = self._candidate_window_ids(
                xdotool,
                observed_family_pids,
                normalized_hints,
                known_window_ids,
            )
            candidate = next(iter(candidates), None)
            if candidate is not None:
                # Stage the still-hidden window off-screen, then ensure it remains
                # unmapped until the reparent transaction maps it inside the panel.
                try:
                    self._run_xdotool(xdotool, "windowmove", candidate, "-32000", "-32000")
                except PanelLaunchError:
                    LOGGER.debug("Could not stage terminal window off-screen.")
                try:
                    self._run_xdotool(xdotool, "windowunmap", candidate)
                except PanelLaunchError:
                    LOGGER.debug("Terminal window was not mapped when first discovered.")
                return candidate
            time.sleep(self._poll_interval)

        LOGGER.warning(
            "No terminal X11 window was discovered before the %.2fs deadline for PID %s.",
            self._launch_timeout,
            process.pid,
        )
        return None

    def _embed_window(
        self,
        xdotool: str,
        xwininfo: str,
        window_id: str,
        parent_window_id: int,
        panel_id: str,
    ) -> bool:
        for attempt in range(1, self._reparent_attempts + 1):
            try:
                try:
                    self._run_xdotool(xdotool, "windowunmap", window_id)
                except PanelLaunchError:
                    pass
                self._run_xdotool(
                    xdotool,
                    "windowreparent",
                    window_id,
                    str(parent_window_id),
                )
                self._run_xdotool(xdotool, "windowmove", window_id, "0", "0")
                self._run_xdotool(xdotool, "windowmap", window_id)
            except PanelLaunchError:
                LOGGER.warning(
                    "Embedded terminal transaction %s failed for panel %s.",
                    attempt,
                    panel_id,
                    exc_info=True,
                )
            else:
                if self._confirm_window_parent(xwininfo, window_id, parent_window_id):
                    return True
            time.sleep(max(0.02, self._poll_interval))
        return False


class EmbeddedOnlyTerminalBackend(X11TerminalBackend):
    """Never leave a terminal in an external fallback window."""

    def __init__(self) -> None:
        super().__init__(EmbeddedFirstX11PanelRuntimeBackend())

    def launch(
        self,
        panel_id: str,
        title: str,
        shell_command: tuple[str, ...],
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        shell = resolve_command(shell_command)
        emulator = self._terminal_emulator()
        if emulator is None:
            raise TerminalEngineError("Nenhum emulador de terminal compatível foi encontrado.")

        token = safe_panel_token(panel_id)
        unique_title = f"TriView Terminal [{token}]"
        command = self._build_command(emulator, unique_title or title, shell)
        request = PanelRuntimeLaunchRequest(
            panel_id=panel_id,
            command=command,
            window_hints=(
                unique_title,
                title,
                Path(emulator).name,
                token,
                panel_id,
            ),
            allow_external_fallback=False,
        )
        return self._runtime.launch(request, parent_window_id)


def build_embedded_terminal_controller() -> TerminalRuntimeController:
    """Return the terminal controller used by the approved RC4 shell."""

    return TerminalRuntimeController(TerminalEngine(EmbeddedOnlyTerminalBackend()))


__all__ = [
    "EmbeddedFirstX11PanelRuntimeBackend",
    "EmbeddedOnlyTerminalBackend",
    "build_embedded_terminal_controller",
]
