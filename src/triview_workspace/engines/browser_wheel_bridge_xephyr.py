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
_ANCESTRY_CACHE_MAX_ENTRIES = 512
_ANCESTRY_CACHE: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {}
_ANCESTRY_CACHE_LOCK = threading.RLock()


@dataclass(frozen=True, slots=True)
class XephyrBrowserWheelRoute:
    runtime_id: str
    host_window_id: int
    browser_window_id: str
    host_ancestry: tuple[int, ...] = ()
    browser_ancestry: tuple[int, ...] = ()

    def as_payload(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "host_window_id": int(self.host_window_id),
            "browser_window_id": str(self.browser_window_id),
            "host_ancestry": list(self.host_ancestry),
            "browser_ancestry": list(self.browser_ancestry),
        }


def clear_x11_ancestry_cache() -> None:
    """Discard cached X11 ancestry after topology-changing operations or tests."""

    with _ANCESTRY_CACHE_LOCK:
        _ANCESTRY_CACHE.clear()


def _cached_ancestry(
    key: tuple[int, int],
    now: float,
) -> tuple[int, ...] | None:
    with _ANCESTRY_CACHE_LOCK:
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
    with _ANCESTRY_CACHE_LOCK:
        _ANCESTRY_CACHE[key] = (now, ancestry)
        if len(_ANCESTRY_CACHE) <= _ANCESTRY_CACHE_MAX_ENTRIES:
            return
        ordered = sorted(
            _ANCESTRY_CACHE.items(),
            key=lambda item: item[1][0],
        )
        overflow = len(_ANCESTRY_CACHE) - _ANCESTRY_CACHE_MAX_ENTRIES
        for stale_key, _value in ordered[:overflow]:
            _ANCESTRY_CACHE.pop(stale_key, None)


def x11_window_ancestry(window_id: int | str, *, max_depth: int = 24) -> tuple[int, ...]:
    """Return the window and its host-display ancestors with a short TTL cache.

    Route publication runs several times per second. Without caching, every
    publication spawned one ``xwininfo`` process per ancestor and per panel,
    which could itself become a measurable CPU/process source with six live
    Browser Panels. The cache preserves current topology while bounding probes.
    """

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
            ancestry_cache_ttl_seconds=_ANCESTRY_CACHE_TTL_SECONDS,
        )


__all__ = [
    "XephyrBrowserWheelBridge",
    "XephyrBrowserWheelRoute",
    "clear_x11_ancestry_cache",
    "x11_window_ancestry",
]
