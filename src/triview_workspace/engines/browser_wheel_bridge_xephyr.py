"""Wheel bridge metadata for nested Xephyr Browser Panels."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

from triview_workspace.engines.browser_wheel_bridge import BrowserWheelBridge
from triview_workspace.runtime_observability import record_runtime_event


_ANCESTRY_CACHE_TTL_SECONDS = 5.0
_GEOMETRY_CACHE_TTL_SECONDS = 1.0
_CACHE_MAX_ENTRIES = 512
_ANCESTRY_CACHE: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {}
_GEOMETRY_CACHE: dict[int, tuple[float, "X11WindowGeometry | None"]] = {}
_ROUTE_CACHE_LOCK = threading.RLock()


@dataclass(frozen=True, slots=True)
class X11WindowGeometry:
    x: int
    y: int
    width: int
    height: int

    def contains(self, pointer_x: int, pointer_y: int) -> bool:
        return bool(
            self.width > 0
            and self.height > 0
            and self.x <= pointer_x < self.x + self.width
            and self.y <= pointer_y < self.y + self.height
        )


@dataclass(frozen=True, slots=True)
class XephyrBrowserWheelRoute:
    runtime_id: str
    host_window_id: int
    browser_window_id: str
    host_ancestry: tuple[int, ...] = ()
    browser_ancestry: tuple[int, ...] = ()
    host_x: int | None = None
    host_y: int | None = None
    host_width: int | None = None
    host_height: int | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "host_window_id": int(self.host_window_id),
            "browser_window_id": str(self.browser_window_id),
            "host_ancestry": list(self.host_ancestry),
            "browser_ancestry": list(self.browser_ancestry),
            "host_x": self.host_x,
            "host_y": self.host_y,
            "host_width": self.host_width,
            "host_height": self.host_height,
        }


def clear_x11_route_cache() -> None:
    """Discard cached ancestry and geometry after X11 topology changes."""

    with _ROUTE_CACHE_LOCK:
        _ANCESTRY_CACHE.clear()
        _GEOMETRY_CACHE.clear()


def clear_x11_ancestry_cache() -> None:
    """Compatibility alias retained for existing callers and tests."""

    clear_x11_route_cache()


def _cached_ancestry(
    key: tuple[int, int],
    now: float,
) -> tuple[int, ...] | None:
    with _ROUTE_CACHE_LOCK:
        cached = _ANCESTRY_CACHE.get(key)
        if cached is None:
            return None
        observed_at, ancestry = cached
        if now - observed_at <= _ANCESTRY_CACHE_TTL_SECONDS:
            return ancestry
        _ANCESTRY_CACHE.pop(key, None)
    return None


def _store_ancestry(
    key: tuple[int, int],
    now: float,
    ancestry: tuple[int, ...],
) -> None:
    with _ROUTE_CACHE_LOCK:
        _ANCESTRY_CACHE[key] = (now, ancestry)
        _prune_cache(_ANCESTRY_CACHE)


def _prune_cache(cache: dict[Any, tuple[float, Any]]) -> None:
    if len(cache) <= _CACHE_MAX_ENTRIES:
        return
    ordered = sorted(cache.items(), key=lambda item: item[1][0])
    overflow = len(cache) - _CACHE_MAX_ENTRIES
    for stale_key, _value in ordered[:overflow]:
        cache.pop(stale_key, None)


def x11_window_ancestry(window_id: int | str, *, max_depth: int = 24) -> tuple[int, ...]:
    """Return the window and its host-display ancestors with a short TTL cache."""

    xwininfo = shutil.which("xwininfo")
    if xwininfo is None:
        return ()
    try:
        normalized_window_id = int(str(window_id), 0)
    except ValueError:
        return ()
    safe_depth = max(1, int(max_depth))
    key = (normalized_window_id, safe_depth)
    now = time.monotonic()
    cached = _cached_ancestry(key, now)
    if cached is not None:
        return cached

    current = normalized_window_id
    ancestry: list[int] = []
    for _depth in range(safe_depth):
        if current in ancestry or current <= 0:
            break
        ancestry.append(current)
        result = subprocess.run(
            [xwininfo, "-id", str(current), "-tree"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        if result.returncode != 0:
            break
        match = re.search(
            r"Parent window id:\s*(0x[0-9a-fA-F]+|\d+)",
            result.stdout,
        )
        if match is None:
            break
        try:
            parent = int(match.group(1), 0)
        except ValueError:
            break
        if parent == current:
            break
        current = parent
    resolved = tuple(ancestry)
    _store_ancestry(key, now, resolved)
    return resolved


def x11_window_geometry(window_id: int | str) -> X11WindowGeometry | None:
    """Return root-relative host bounds with a one-second probe cache."""

    xwininfo = shutil.which("xwininfo")
    if xwininfo is None:
        return None
    try:
        normalized_window_id = int(str(window_id), 0)
    except ValueError:
        return None
    now = time.monotonic()
    with _ROUTE_CACHE_LOCK:
        cached = _GEOMETRY_CACHE.get(normalized_window_id)
        if cached is not None and now - cached[0] <= _GEOMETRY_CACHE_TTL_SECONDS:
            return cached[1]
        if cached is not None:
            _GEOMETRY_CACHE.pop(normalized_window_id, None)

    result = subprocess.run(
        [xwininfo, "-id", str(normalized_window_id)],
        capture_output=True,
        text=True,
        check=False,
        timeout=2,
    )
    geometry: X11WindowGeometry | None = None
    if result.returncode == 0:
        fields: dict[str, int] = {}
        patterns = {
            "x": r"Absolute upper-left X:\s*(-?\d+)",
            "y": r"Absolute upper-left Y:\s*(-?\d+)",
            "width": r"Width:\s*(\d+)",
            "height": r"Height:\s*(\d+)",
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, result.stdout)
            if match is not None:
                fields[key] = int(match.group(1))
        if set(fields) == {"x", "y", "width", "height"}:
            geometry = X11WindowGeometry(**fields)

    with _ROUTE_CACHE_LOCK:
        _GEOMETRY_CACHE[normalized_window_id] = (now, geometry)
        _prune_cache(_GEOMETRY_CACHE)
    return geometry


class XephyrBrowserWheelBridge(BrowserWheelBridge):
    """Start the ancestry-aware correlated worker."""

    def start(self) -> None:
        if self._closed or self._process is not None:
            return
        try:
            process = subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "triview_workspace.engines.browser_wheel_worker_xephyr",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=os.environ.copy(),
            )
        except OSError as exc:
            record_runtime_event(
                "wheel_bridge_start_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            return
        self._process = process
        self._reader_thread = threading.Thread(
            target=self._read_stdout,
            name="triview-xephyr-wheel-bridge-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="triview-xephyr-wheel-bridge-stderr",
            daemon=True,
        )
        self._reader_thread.start()
        self._stderr_thread.start()
        record_runtime_event(
            "wheel_bridge_process_started",
            pid=process.pid,
            captures_keyboard=False,
            captures_only_buttons=[4, 5],
            worker_module="triview_workspace.engines.browser_wheel_worker_xephyr",
            route_ancestry=True,
            route_geometry=True,
            ancestry_cache_ttl_seconds=_ANCESTRY_CACHE_TTL_SECONDS,
            geometry_cache_ttl_seconds=_GEOMETRY_CACHE_TTL_SECONDS,
        )


__all__ = [
    "X11WindowGeometry",
    "XephyrBrowserWheelBridge",
    "XephyrBrowserWheelRoute",
    "clear_x11_ancestry_cache",
    "clear_x11_route_cache",
    "x11_window_ancestry",
    "x11_window_geometry",
]
