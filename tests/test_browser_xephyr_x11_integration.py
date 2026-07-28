from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path

import pytest

from triview_workspace.engines.browser_embedded import terminate_process_group
from triview_workspace.engines.browser_xephyr_managed import (
    ManagedXephyrEmbeddedBraveBrowserBackend,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("TRIVIEW_RUN_XEPHYR_INTEGRATION") != "1",
    reason="Xephyr integration runs only in the dedicated X11 CI step",
)


def test_nested_client_is_contained_and_receives_host_wheel(
    tmp_path: Path,
) -> None:
    xephyr = shutil.which("Xephyr")
    xdotool = shutil.which("xdotool")
    xwininfo = shutil.which("xwininfo")
    if not xephyr or not xdotool or not xwininfo or not os.environ.get("DISPLAY"):
        pytest.skip("Xephyr/X11 dependencies unavailable")

    root = tk.Tk()
    root.geometry("640x480+20+20")
    host = tk.Frame(root, width=480, height=320)
    host.pack(fill="both", expand=True)
    root.update_idletasks()
    root.update()

    backend = ManagedXephyrEmbeddedBraveBrowserBackend(launch_timeout=12.0)
    _display_number, display_name, lock_path = backend._allocate_display()
    process = subprocess.Popen(
        [
            xephyr,
            display_name,
            "-parent",
            str(host.winfo_id()),
            "-screen",
            "480x320",
            "-resizeable",
            "-noreset",
            "-nolisten",
            "tcp",
            "-ac",
            "-br",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    nested_client: subprocess.Popen[bytes] | None = None
    marker = tmp_path / "nested-wheel.txt"
    try:
        backend._wait_for_display(display_name, process)
        xephyr_window_id = backend._wait_for_host_window(
            xdotool,
            process,
            host.winfo_id(),
        )
        nested_env = os.environ.copy()
        nested_env["DISPLAY"] = display_name
        nested_env.pop("WAYLAND_DISPLAY", None)
        nested_client = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import pathlib,sys,tkinter as tk; "
                    "marker=pathlib.Path(sys.argv[1]); "
                    "root=tk.Tk(); root.title('TRIVIEW_NESTED_TEST_CLIENT'); "
                    "root.geometry('320x220+0+0'); "
                    "root.bind('<ButtonRelease-5>', lambda event: "
                    "marker.write_text(str(event.num), encoding='utf-8')); "
                    "root.after(10000, root.destroy); root.mainloop()"
                ),
                str(marker),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=nested_env,
            start_new_session=True,
        )

        deadline = time.monotonic() + 8.0
        nested_window_id = ""
        while time.monotonic() < deadline:
            result = subprocess.run(
                [xdotool, "search", "--onlyvisible", "--name", "TRIVIEW_NESTED_TEST_CLIENT"],
                capture_output=True,
                text=True,
                check=False,
                env=nested_env,
                timeout=2,
            )
            candidates = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if candidates:
                nested_window_id = candidates[-1]
                break
            time.sleep(0.05)

        assert nested_window_id
        host_tree = subprocess.run(
            [xwininfo, "-root", "-tree"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout
        assert "TRIVIEW_NESTED_TEST_CLIENT" not in host_tree
        assert backend._is_descendant_of(
            xwininfo,
            xephyr_window_id,
            host.winfo_id(),
        )

        subprocess.run(
            [xdotool, "mousemove", "--window", xephyr_window_id, "120", "120"],
            check=True,
            timeout=3,
        )
        subprocess.run(
            [xdotool, "click", "--window", xephyr_window_id, "5"],
            check=True,
            timeout=3,
        )
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(0.05)
        assert marker.read_text(encoding="utf-8") == "5"
    finally:
        if nested_client is not None:
            terminate_process_group(nested_client)
        terminate_process_group(process)
        backend._release_display(lock_path)
        root.destroy()
