"""Reliable host-window discovery for Xephyr embedded through ``-parent``."""

from __future__ import annotations

import re
import shutil
import subprocess
import time

from triview_workspace.engines.browser import BrowserLaunchError
from triview_workspace.engines.browser_xephyr import (
    XEPHYR_BROWSER_BACKEND_NAME,
    XephyrEmbeddedBraveBrowserBackend,
)


class ManagedXephyrEmbeddedBraveBrowserBackend(XephyrEmbeddedBraveBrowserBackend):
    """Find the Xephyr child by the actual host tree, not only ``_NET_WM_PID``."""

    def _wait_for_host_window(
        self,
        xdotool: str,
        process: subprocess.Popen[bytes],
        parent_window_id: int,
    ) -> str:
        xwininfo = shutil.which("xwininfo")
        if xwininfo is None:
            raise BrowserLaunchError("xwininfo não está disponível para localizar o Xephyr.")
        deadline = time.monotonic() + self._launch_timeout
        while time.monotonic() < deadline:
            direct_children = self._direct_children(xwininfo, parent_window_id)
            for window_id in direct_children:
                if self._looks_like_xephyr(xdotool, window_id, process.pid):
                    return window_id

            # Some X servers wrap the embedded client in one intermediate child.
            candidates: list[str] = []
            for selector, value in (
                ("--class", r"^Xephyr$"),
                ("--classname", r"^Xephyr$"),
                ("--name", r"Xephyr"),
            ):
                result = subprocess.run(
                    [xdotool, "search", selector, value],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=2,
                )
                if result.returncode not in (0, 1):
                    continue
                candidates.extend(
                    line.strip() for line in result.stdout.splitlines() if line.strip()
                )
            for window_id in reversed(candidates):
                if self._is_descendant_of(xwininfo, window_id, parent_window_id):
                    return window_id

            if process.poll() is not None:
                break
            time.sleep(0.04)
        raise BrowserLaunchError(
            "A janela hospedeira do Xephyr não foi localizada dentro do painel."
        )

    @staticmethod
    def _direct_children(xwininfo: str, parent_window_id: int) -> list[str]:
        result = subprocess.run(
            [xwininfo, "-id", str(int(parent_window_id)), "-children"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        if result.returncode != 0:
            return []
        ordered: list[str] = []
        seen: set[str] = set()
        for line in result.stdout.splitlines():
            match = re.match(r"\s*(0x[0-9a-fA-F]+)\s", line)
            if match is None:
                continue
            window_id = str(int(match.group(1), 0))
            if window_id not in seen:
                seen.add(window_id)
                ordered.append(window_id)
        return ordered

    @staticmethod
    def _looks_like_xephyr(xdotool: str, window_id: str, expected_pid: int) -> bool:
        values: dict[str, str] = {}
        for operation in ("getwindowpid", "getwindowname", "getwindowclassname"):
            result = subprocess.run(
                [xdotool, operation, window_id],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            values[operation] = result.stdout.strip() if result.returncode == 0 else ""
        try:
            pid_matches = int(values["getwindowpid"]) == int(expected_pid)
        except ValueError:
            pid_matches = False
        identity = " ".join(
            (values["getwindowname"], values["getwindowclassname"])
        ).casefold()
        return pid_matches or "xephyr" in identity


__all__ = [
    "ManagedXephyrEmbeddedBraveBrowserBackend",
    "XEPHYR_BROWSER_BACKEND_NAME",
]
