"""Isolated X11 passive-grab worker for embedded Browser wheel routing.

This module runs in a dedicated subprocess. It grabs only wheel buttons 4 and 5
on registered TriView host windows, forwards exactly one synthetic wheel event
to the corresponding embedded Chromium child and never observes keyboard input.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import select
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Any

BUTTON_PRESS = 4
BUTTON_RELEASE = 5
BUTTON_PRESS_MASK = 1 << 2
BUTTON_RELEASE_MASK = 1 << 3
GRAB_MODE_ASYNC = 1
ANY_MODIFIER = 1 << 15
WHEEL_BUTTONS = (4, 5)


class XButtonEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("button", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class XEvent(ctypes.Union):
    _fields_ = [
        ("type", ctypes.c_int),
        ("xbutton", XButtonEvent),
        ("pad", ctypes.c_long * 24),
    ]


class XErrorEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("resourceid", ctypes.c_ulong),
        ("serial", ctypes.c_ulong),
        ("error_code", ctypes.c_ubyte),
        ("request_code", ctypes.c_ubyte),
        ("minor_code", ctypes.c_ubyte),
    ]


@dataclass(frozen=True, slots=True)
class WheelRoute:
    runtime_id: str
    host_window_id: int
    browser_window_id: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "WheelRoute":
        return cls(
            runtime_id=str(payload["runtime_id"]),
            host_window_id=int(payload["host_window_id"]),
            browser_window_id=str(payload["browser_window_id"]),
        )

    def as_payload(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "host_window_id": self.host_window_id,
            "browser_window_id": self.browser_window_id,
        }


def emit(event_type: str, **fields: Any) -> None:
    payload = {"event_type": event_type, **fields}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()


def load_x11() -> ctypes.CDLL:
    library_name = ctypes.util.find_library("X11")
    if not library_name:
        raise RuntimeError("libX11 não encontrada")
    library = ctypes.CDLL(library_name)
    library.XOpenDisplay.argtypes = [ctypes.c_char_p]
    library.XOpenDisplay.restype = ctypes.c_void_p
    library.XCloseDisplay.argtypes = [ctypes.c_void_p]
    library.XCloseDisplay.restype = ctypes.c_int
    library.XConnectionNumber.argtypes = [ctypes.c_void_p]
    library.XConnectionNumber.restype = ctypes.c_int
    library.XPending.argtypes = [ctypes.c_void_p]
    library.XPending.restype = ctypes.c_int
    library.XNextEvent.argtypes = [ctypes.c_void_p, ctypes.POINTER(XEvent)]
    library.XNextEvent.restype = ctypes.c_int
    library.XGrabButton.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_ulong,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    library.XGrabButton.restype = ctypes.c_int
    library.XUngrabButton.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_ulong,
    ]
    library.XUngrabButton.restype = ctypes.c_int
    library.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.XSync.restype = ctypes.c_int
    return library


class WheelWorker:
    def __init__(self) -> None:
        self.xdotool = shutil.which("xdotool")
        if self.xdotool is None:
            raise RuntimeError("xdotool não encontrado")
        if not os.environ.get("DISPLAY"):
            raise RuntimeError("DISPLAY ausente")
        self.x11 = load_x11()
        self.display = self.x11.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("não foi possível abrir o display X11")
        self.connection_fd = int(self.x11.XConnectionNumber(self.display))
        self.routes: dict[int, WheelRoute] = {}
        self.running = True

    def close(self) -> None:
        for route in tuple(self.routes.values()):
            self._ungrab_route(route)
        self.routes.clear()
        if self.display:
            self.x11.XSync(self.display, 0)
            self.x11.XCloseDisplay(self.display)
            self.display = None

    def run(self) -> int:
        emit("wheel_bridge_ready", display=os.environ.get("DISPLAY"))
        stdin_fd = sys.stdin.fileno()
        while self.running:
            readable, _writable, _errors = select.select(
                [stdin_fd, self.connection_fd],
                [],
                [],
                0.20,
            )
            if stdin_fd in readable:
                line = sys.stdin.readline()
                if not line:
                    break
                self._handle_command(line)
            if self.connection_fd in readable:
                self._drain_x_events()
        return 0

    def _handle_command(self, line: str) -> None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            emit("wheel_bridge_command_rejected", reason="invalid_json")
            return
        action = payload.get("action")
        if action == "stop":
            self.running = False
            return
        if action != "sync":
            emit("wheel_bridge_command_rejected", reason="unknown_action")
            return
        routes: dict[int, WheelRoute] = {}
        try:
            for item in payload.get("routes", []):
                route = WheelRoute.from_payload(item)
                routes[route.host_window_id] = route
        except (KeyError, TypeError, ValueError) as exc:
            emit("wheel_bridge_command_rejected", reason=str(exc))
            return
        self._sync_routes(routes)

    def _sync_routes(self, desired: dict[int, WheelRoute]) -> None:
        for host_window_id, existing in tuple(self.routes.items()):
            replacement = desired.get(host_window_id)
            if replacement == existing:
                continue
            self._ungrab_route(existing)
            self.routes.pop(host_window_id, None)
            emit("wheel_route_removed", **existing.as_payload())
        for host_window_id, route in desired.items():
            if self.routes.get(host_window_id) == route:
                continue
            self._grab_route(route)
            self.routes[host_window_id] = route
            emit("wheel_route_registered", **route.as_payload())
        self.x11.XSync(self.display, 0)

    def _grab_route(self, route: WheelRoute) -> None:
        for button in WHEEL_BUTTONS:
            self.x11.XGrabButton(
                self.display,
                button,
                ANY_MODIFIER,
                route.host_window_id,
                0,
                BUTTON_PRESS_MASK | BUTTON_RELEASE_MASK,
                GRAB_MODE_ASYNC,
                GRAB_MODE_ASYNC,
                0,
                0,
            )

    def _ungrab_route(self, route: WheelRoute) -> None:
        for button in WHEEL_BUTTONS:
            self.x11.XUngrabButton(
                self.display,
                button,
                ANY_MODIFIER,
                route.host_window_id,
            )

    def _drain_x_events(self) -> None:
        while self.x11.XPending(self.display) > 0:
            event = XEvent()
            self.x11.XNextEvent(self.display, ctypes.byref(event))
            if event.type != BUTTON_RELEASE:
                continue
            button = int(event.xbutton.button)
            if button not in WHEEL_BUTTONS:
                continue
            host_window_id = int(event.xbutton.window)
            route = self.routes.get(host_window_id)
            if route is None:
                emit(
                    "wheel_event_unrouted",
                    host_window_id=host_window_id,
                    button=button,
                )
                continue
            self._forward(route, button, int(event.xbutton.x_root), int(event.xbutton.y_root))

    def _forward(
        self,
        route: WheelRoute,
        button: int,
        pointer_x: int,
        pointer_y: int,
    ) -> None:
        # Remove only the active passive grab while xdotool emits one event to
        # the child. Re-grabbing after xdotool exits prevents feedback loops and
        # ensures the original physical event is replaced by exactly one event.
        self.x11.XUngrabButton(
            self.display,
            button,
            ANY_MODIFIER,
            route.host_window_id,
        )
        self.x11.XSync(self.display, 0)
        try:
            result = subprocess.run(
                [
                    self.xdotool,
                    "click",
                    "--window",
                    route.browser_window_id,
                    button,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=2,
            )
            delivered = result.returncode == 0
            error = result.stderr.strip()[:300] if not delivered else ""
        except (OSError, subprocess.SubprocessError) as exc:
            delivered = False
            error = str(exc)[:300]
        finally:
            self.x11.XGrabButton(
                self.display,
                button,
                ANY_MODIFIER,
                route.host_window_id,
                0,
                BUTTON_PRESS_MASK | BUTTON_RELEASE_MASK,
                GRAB_MODE_ASYNC,
                GRAB_MODE_ASYNC,
                0,
                0,
            )
            self.x11.XSync(self.display, 0)
        emit(
            "wheel_event_forwarded",
            **route.as_payload(),
            button=button,
            steps=1 if button == 4 else -1,
            pointer_x=pointer_x,
            pointer_y=pointer_y,
            delivered=delivered,
            error=error,
        )


def main() -> int:
    try:
        worker = WheelWorker()
    except Exception as exc:  # noqa: BLE001
        emit("wheel_bridge_unavailable", error=str(exc))
        return 2
    try:
        return worker.run()
    except Exception as exc:  # noqa: BLE001
        emit("wheel_bridge_failed", error=f"{type(exc).__name__}: {exc}")
        return 1
    finally:
        worker.close()


if __name__ == "__main__":
    raise SystemExit(main())
