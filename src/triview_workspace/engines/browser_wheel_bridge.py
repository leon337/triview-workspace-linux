"""Parent-side lifecycle for the isolated X11 Browser wheel bridge."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Any, Iterable

from triview_workspace.runtime_observability import record_runtime_event


@dataclass(frozen=True, slots=True)
class BrowserWheelRoute:
    runtime_id: str
    host_window_id: int
    browser_window_id: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "host_window_id": int(self.host_window_id),
            "browser_window_id": str(self.browser_window_id),
        }


class BrowserWheelBridge:
    """Synchronize Browser routes with a keyboard-blind X11 subprocess."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._writer_lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._closed = False
        self._last_routes: tuple[BrowserWheelRoute, ...] = ()

    def start(self) -> None:
        if self._closed or self._process is not None:
            return
        try:
            process = subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "triview_workspace.engines.browser_wheel_worker_rc",
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
            name="triview-wheel-bridge-stdout",
            daemon=True,
        )
        self._stderr_thread = threading.Thread(
            target=self._read_stderr,
            name="triview-wheel-bridge-stderr",
            daemon=True,
        )
        self._reader_thread.start()
        self._stderr_thread.start()
        record_runtime_event(
            "wheel_bridge_process_started",
            pid=process.pid,
            captures_keyboard=False,
            captures_only_buttons=[4, 5],
            worker_module="triview_workspace.engines.browser_wheel_worker_rc",
        )

    def sync(self, routes: Iterable[BrowserWheelRoute]) -> None:
        normalized = tuple(
            sorted(
                routes,
                key=lambda item: (
                    item.host_window_id,
                    item.runtime_id,
                    item.browser_window_id,
                ),
            )
        )
        if normalized == self._last_routes:
            return
        self._last_routes = normalized
        self._send(
            {
                "action": "sync",
                "routes": [route.as_payload() for route in normalized],
            }
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._send({"action": "stop"})
        process = self._process
        if process is None:
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
        record_runtime_event(
            "wheel_bridge_process_stopped",
            pid=process.pid,
            returncode=process.returncode,
        )
        self._process = None

    def _send(self, payload: dict[str, Any]) -> None:
        process = self._process
        if self._closed and payload.get("action") != "stop":
            return
        if process is None or process.poll() is not None or process.stdin is None:
            return
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"
        try:
            with self._writer_lock:
                process.stdin.write(line)
                process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            record_runtime_event(
                "wheel_bridge_command_failed",
                action=payload.get("action"),
                error_type=type(exc).__name__,
                error=str(exc),
            )

    def _read_stdout(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                record_runtime_event(
                    "wheel_bridge_output_invalid",
                    output_length=len(line),
                )
                continue
            if not isinstance(payload, dict):
                continue
            event_type = str(payload.pop("event_type", "wheel_bridge_event"))
            record_runtime_event(event_type, **payload)

    def _read_stderr(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for line in process.stderr:
            stripped = line.strip()
            if not stripped:
                continue
            record_runtime_event(
                "wheel_bridge_stderr",
                message=stripped[:500],
            )


__all__ = ["BrowserWheelBridge", "BrowserWheelRoute"]
