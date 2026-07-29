"""Atomic embedded-only terminal runtime for the RC4 desktop candidate."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Sequence
from pathlib import Path

from triview_workspace.engines.browser_embedded import (
    STAGING_COORDINATE,
    exact_x11_pattern,
    terminate_process_group,
)
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

TERMINAL_POLL_INTERVAL = 0.02


def build_staged_terminal_command(
    emulator: str,
    title: str,
    shell_command: tuple[str, ...],
) -> tuple[str, ...]:
    """Build an emulator command whose first window starts outside the desktop."""

    name = Path(emulator).name
    geometry_chars = f"80x24{STAGING_COORDINATE}{STAGING_COORDINATE}"
    geometry_pixels = f"800x600{STAGING_COORDINATE}{STAGING_COORDINATE}"

    if name == "xterm":
        return (emulator, "-geometry", geometry_chars, "-T", title, "-e", *shell_command)
    if name == "xfce4-terminal":
        return (
            emulator,
            "--disable-server",
            f"--title={title}",
            f"--geometry={geometry_chars}",
            "--execute",
            *shell_command,
        )
    if name == "gnome-terminal":
        return (
            emulator,
            f"--title={title}",
            f"--geometry={geometry_chars}",
            "--",
            *shell_command,
        )
    if name == "kitty":
        return (
            emulator,
            "--single-instance=no",
            "--title",
            title,
            "--override",
            "remember_window_size=no",
            "--override",
            "initial_window_width=800",
            "--override",
            "initial_window_height=600",
            *shell_command,
        )
    if name == "alacritty":
        return (
            emulator,
            "--title",
            title,
            "--position",
            str(STAGING_COORDINATE),
            str(STAGING_COORDINATE),
            "-e",
            *shell_command,
        )
    if name == "konsole":
        return (
            emulator,
            "--geometry",
            geometry_pixels,
            "-p",
            f"tabtitle={title}",
            "-e",
            *shell_command,
        )
    return (emulator, "-e", *shell_command)


class EmbeddedFirstX11PanelRuntimeBackend(X11PanelRuntimeBackend):
    """Select only the unique terminal window and reparent it before mapping."""

    def __init__(self) -> None:
        super().__init__(
            launch_timeout=14.0,
            poll_interval=TERMINAL_POLL_INTERVAL,
            reparent_attempts=12,
            stable_parent_checks=2,
        )

    def _wait_for_window(
        self,
        xdotool: str,
        xwininfo: str,
        process: subprocess.Popen[bytes],
        hints: Sequence[str],
        known_window_ids: set[str],
    ) -> str | None:
        del xwininfo
        deadline = time.monotonic() + self._launch_timeout
        unique_title = hints[0] if hints else ""
        title_pattern = exact_x11_pattern(unique_title)
        observed_family_pids = {int(process.pid)}
        process_exit_seen_at: float | None = None

        while time.monotonic() < deadline:
            observed_family_pids.update(self._process_family(process.pid))
            candidates = [
                window_id
                for window_id in self._search_windows(
                    xdotool,
                    "--name",
                    title_pattern,
                    only_visible=False,
                )
                if window_id not in known_window_ids
            ]

            family_candidates: list[str] = []
            unknown_pid_candidates: list[str] = []
            for window_id in candidates:
                window_pid = self._window_pid(xdotool, window_id)
                if window_pid in observed_family_pids:
                    family_candidates.append(window_id)
                elif window_pid is None:
                    unknown_pid_candidates.append(window_id)

            candidate = next(iter(family_candidates), None)
            if candidate is None and len(unknown_pid_candidates) == 1:
                candidate = unknown_pid_candidates[0]

            if candidate is not None:
                self._stage_window(xdotool, candidate)
                return candidate

            if process.poll() is not None:
                if process_exit_seen_at is None:
                    process_exit_seen_at = time.monotonic()
                elif time.monotonic() - process_exit_seen_at >= 1.5:
                    break
            time.sleep(self._poll_interval)

        return None

    def _stage_window(self, xdotool: str, window_id: str) -> None:
        try:
            self._run_xdotool(xdotool, "windowunmap", window_id)
        except PanelLaunchError:
            pass
        try:
            self._run_xdotool(
                xdotool,
                "windowmove",
                window_id,
                str(STAGING_COORDINATE),
                str(STAGING_COORDINATE),
            )
        except PanelLaunchError:
            pass

    def _embed_window(
        self,
        xdotool: str,
        xwininfo: str,
        window_id: str,
        parent_window_id: int,
        panel_id: str,
    ) -> bool:
        del panel_id
        for _attempt in range(1, self._reparent_attempts + 1):
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
                if not self._confirm_window_parent(
                    xwininfo,
                    window_id,
                    parent_window_id,
                ):
                    time.sleep(self._poll_interval)
                    continue
                self._run_xdotool(xdotool, "windowmap", window_id)
                return True
            except PanelLaunchError:
                time.sleep(self._poll_interval)
        return False

    @staticmethod
    def _terminate_process(process: subprocess.Popen[bytes]) -> None:
        terminate_process_group(process)


class EmbeddedOnlyTerminalBackend(X11TerminalBackend):
    """Never leave a terminal in an external fallback window."""

    def __init__(self) -> None:
        super().__init__(EmbeddedFirstX11PanelRuntimeBackend())

    @staticmethod
    def _build_command(
        emulator: str,
        title: str,
        shell_command: tuple[str, ...],
    ) -> tuple[str, ...]:
        return build_staged_terminal_command(emulator, title, shell_command)

    def launch(
        self,
        panel_id: str,
        title: str,
        shell_command: tuple[str, ...],
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        del title
        shell = resolve_command(shell_command)
        emulator = self._terminal_emulator()
        if emulator is None:
            raise TerminalEngineError("Nenhum emulador de terminal compatível foi encontrado.")

        token = safe_panel_token(panel_id)
        unique_title = f"TriView-Terminal-{token}"
        command = self._build_command(emulator, unique_title, shell)
        request = PanelRuntimeLaunchRequest(
            panel_id=panel_id,
            command=command,
            window_hints=(unique_title,),
            allow_external_fallback=False,
        )
        return self._runtime.launch(request, parent_window_id)


def build_embedded_terminal_controller() -> TerminalRuntimeController:
    """Return the atomic terminal controller used by the approved RC4 shell."""

    return TerminalRuntimeController(TerminalEngine(EmbeddedOnlyTerminalBackend()))


__all__ = [
    "EmbeddedFirstX11PanelRuntimeBackend",
    "EmbeddedOnlyTerminalBackend",
    "TERMINAL_POLL_INTERVAL",
    "build_embedded_terminal_controller",
    "build_staged_terminal_command",
]
