from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import select
import shutil
import subprocess
import sys
import time
from typing import Any

import pytest

from triview_workspace.engines.browser_wheel_worker import (
    BUTTON_PRESS_MASK,
    BUTTON_RELEASE,
    BUTTON_RELEASE_MASK,
    XEvent,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("TRIVIEW_RUN_X11_INTEGRATION") != "1",
    reason="executado somente na etapa X11 dedicada da CI",
)


def _load_x11() -> ctypes.CDLL:
    name = ctypes.util.find_library("X11")
    if not name:
        pytest.skip("libX11 indisponível")
    library = ctypes.CDLL(name)
    library.XOpenDisplay.argtypes = [ctypes.c_char_p]
    library.XOpenDisplay.restype = ctypes.c_void_p
    library.XCloseDisplay.argtypes = [ctypes.c_void_p]
    library.XCloseDisplay.restype = ctypes.c_int
    library.XDefaultScreen.argtypes = [ctypes.c_void_p]
    library.XDefaultScreen.restype = ctypes.c_int
    library.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.XRootWindow.restype = ctypes.c_ulong
    library.XCreateSimpleWindow.argtypes = [
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    library.XCreateSimpleWindow.restype = ctypes.c_ulong
    library.XSelectInput.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_long]
    library.XSelectInput.restype = ctypes.c_int
    library.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    library.XMapWindow.restype = ctypes.c_int
    library.XDestroyWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    library.XDestroyWindow.restype = ctypes.c_int
    library.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.XSync.restype = ctypes.c_int
    library.XPending.argtypes = [ctypes.c_void_p]
    library.XPending.restype = ctypes.c_int
    library.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.POINTER(XEvent)]
    library.XNextEvent.restype = ctypes.c_int
    return library


def _read_json_event(
    process: subprocess.Popen[str],
    event_type: str,
    *,
    timeout: float = 5.0,
) -> dict[str, Any]:
    assert process.stdout is not None
    deadline = time.monotonic() + timeout
    seen: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        readable, _writable, _errors = select.select(
            [process.stdout], [], [], min(0.25, deadline - time.monotonic())
        )
        if not readable:
            continue
        line = process.stdout.readline()
        if not line:
            break
        payload = json.loads(line)
        seen.append(payload)
        if payload.get("event_type") == event_type:
            return payload
    stderr = ""
    if process.poll() is not None and process.stderr is not None:
        stderr = process.stderr.read()
    raise AssertionError(
        f"evento {event_type!r} não recebido; seen={seen!r}; "
        f"returncode={process.poll()!r}; stderr={stderr!r}"
    )


def _drain_button_releases(
    x11: ctypes.CDLL,
    display: ctypes.c_void_p,
    *,
    timeout: float = 2.0,
) -> list[int]:
    windows: list[int] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        x11.XSync(display, 0)
        while x11.XPending(display) > 0:
            event = XEvent()
            x11.XNextEvent(display, ctypes.byref(event))
            if event.type == BUTTON_RELEASE and int(event.xbutton.button) == 5:
                windows.append(int(event.xbutton.window))
        if windows:
            time.sleep(0.15)
            x11.XSync(display, 0)
            continue
        time.sleep(0.02)
    return windows


def test_physical_wheel_route_reaches_only_the_target_x11_child() -> None:
    if not os.environ.get("DISPLAY"):
        pytest.skip("DISPLAY X11 indisponível")
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        pytest.skip("xdotool indisponível")

    x11 = _load_x11()
    display = x11.XOpenDisplay(None)
    assert display
    screen = x11.XDefaultScreen(display)
    root = x11.XRootWindow(display, screen)
    host_one = x11.XCreateSimpleWindow(display, root, 20, 20, 260, 180, 0, 0, 0)
    child_one = x11.XCreateSimpleWindow(display, host_one, 0, 0, 260, 180, 0, 0, 0)
    host_two = x11.XCreateSimpleWindow(display, root, 320, 20, 260, 180, 0, 0, 0)
    child_two = x11.XCreateSimpleWindow(display, host_two, 0, 0, 260, 180, 0, 0, 0)
    for child in (child_one, child_two):
        x11.XSelectInput(
            display,
            child,
            BUTTON_PRESS_MASK | BUTTON_RELEASE_MASK,
        )
    for window in (host_one, child_one, host_two, child_two):
        x11.XMapWindow(display, window)
    x11.XSync(display, 0)

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "triview_workspace.engines.browser_wheel_worker",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=os.environ.copy(),
    )
    try:
        _read_json_event(process, "wheel_bridge_ready")
        assert process.stdin is not None
        process.stdin.write(
            json.dumps(
                {
                    "action": "sync",
                    "routes": [
                        {
                            "runtime_id": "workspace::one",
                            "host_window_id": int(host_one),
                            "browser_window_id": str(int(child_one)),
                        },
                        {
                            "runtime_id": "workspace::two",
                            "host_window_id": int(host_two),
                            "browser_window_id": str(int(child_two)),
                        },
                    ],
                }
            )
            + "\n"
        )
        process.stdin.flush()
        _read_json_event(process, "wheel_route_registered")
        _read_json_event(process, "wheel_route_registered")

        subprocess.run(
            [xdotool, "mousemove", "--window", str(int(child_one)), "40", "40"],
            check=True,
            timeout=3,
        )
        subprocess.run([xdotool, "click", "5"], check=True, timeout=3)
        forwarded = _read_json_event(process, "wheel_event_forwarded")
        releases = _drain_button_releases(x11, display)

        assert forwarded["runtime_id"] == "workspace::one"
        assert forwarded["browser_window_id"] == str(int(child_one))
        assert forwarded["button"] == 5
        assert forwarded["delivered"] is True
        assert releases.count(int(child_one)) == 1
        assert int(child_two) not in releases
    finally:
        if process.poll() is None and process.stdin is not None:
            process.stdin.write(json.dumps({"action": "stop"}) + "\n")
            process.stdin.flush()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=2)
        for window in (child_one, host_one, child_two, host_two):
            x11.XDestroyWindow(display, window)
        x11.XSync(display, 0)
        x11.XCloseDisplay(display)
