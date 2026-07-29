"""Explicit, privacy-preserving black-box diagnostics for TriView on X11.

The collector starts only from the diagnostic launcher, shows a visible control
window, records a synchronized technical timeline and produces one local ZIP
package when the user stops the session or the configured timeout expires.
Text contents, passwords, clipboard data and screenshots are never collected.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import tkinter as tk
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

from triview_workspace.runtime_observability import (
    load_candidate_metadata,
    runtime_identity,
    runtime_root,
    state_root,
)

DEFAULT_TIMEOUT_SECONDS = 15 * 60
POLL_INTERVAL_SECONDS = 0.20
PROCESS_INTERVAL_SECONDS = 1.0
WINDOW_INTERVAL_SECONDS = 0.75
MAX_EVENTS_PER_STREAM = 200_000

_SPECIAL_KEY_NAMES = {
    "Escape", "Tab", "Return", "BackSpace", "Delete", "Insert", "Home",
    "End", "Prior", "Next", "Left", "Right", "Up", "Down", "Shift_L",
    "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Super_L",
    "Super_R", "Menu", "Caps_Lock", "Num_Lock", "Scroll_Lock", "Print",
    "Pause", *{f"F{index}" for index in range(1, 13)},
}
_SENSITIVE_TITLE_TERMS = (
    "password", "senha", "token", "secret", "segredo", "bank", "banco",
    "card", "cartão", "cartao",
)


@dataclass(slots=True)
class BlackboxPaths:
    root: Path
    session_summary: Path
    timeline_html: Path
    timeline_jsonl: Path
    user_input_events: Path
    system_events: Path
    triview_events: Path
    x11_window_events: Path
    process_events: Path
    runtime_provenance: Path
    panel_runtime_inventory: Path
    errors: Path
    privacy_report: Path


@dataclass(slots=True)
class StreamWriter:
    path: Path
    handle: TextIO
    count: int = 0
    truncated: bool = False

    def write(self, payload: dict[str, Any]) -> None:
        if self.count >= MAX_EVENTS_PER_STREAM:
            self.truncated = True
            return
        self.handle.write(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n"
        )
        self.handle.flush()
        self.count += 1

    def close(self) -> None:
        self.handle.close()


@dataclass(slots=True)
class CollectorState:
    session_id: str
    started_wall: str
    started_monotonic_ns: int
    stop_reason: str = "user_requested"
    errors: list[str] = field(default_factory=list)
    redactions: Counter[str] = field(default_factory=Counter)
    counts: Counter[str] = field(default_factory=Counter)
    last_pointer_signature: tuple[object, ...] | None = None
    last_active_signature: tuple[object, ...] | None = None
    last_process_snapshot: dict[int, tuple[object, ...]] = field(default_factory=dict)
    last_window_snapshot: dict[str, tuple[object, ...]] = field(default_factory=dict)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def event_base(session_id: str, source: str, event_type: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "timestamp": utc_now(),
        "monotonic_ns": time.monotonic_ns(),
        "source": source,
        "event_type": event_type,
    }


def sanitized_window_title(title: str, redactions: Counter[str]) -> str:
    """Preserve only coarse application identity, not page or conversation titles."""

    normalized = " ".join(title.split())[:240]
    folded = normalized.casefold()
    if any(term in folded for term in _SENSITIVE_TITLE_TERMS):
        redactions["sensitive_window_title"] += 1
        return "[REDACTED_SENSITIVE_TITLE]"
    for marker, public_name in (
        ("chatgpt", "ChatGPT"), ("youtube", "YouTube"),
        ("instagram", "Instagram"), ("github", "GitHub"),
        ("home / x", "X"), ("triview", "TriView Workspace"),
        ("terminal", "Terminal"), ("diagnóstico", "TriView Diagnostic"),
        ("diagnostico", "TriView Diagnostic"),
    ):
        if marker in folded:
            if normalized != public_name:
                redactions["window_title_detail"] += 1
            return public_name
    if not normalized:
        return ""
    redactions["unrecognized_window_title"] += 1
    return "[REDACTED_WINDOW_TITLE]"


def sanitized_arguments(arguments: str, redactions: Counter[str]) -> str:
    """Remove URL query/fragment and explicit secret-like command arguments."""

    safe: list[str] = []
    for token in arguments.split()[:120]:
        folded = token.casefold()
        if any(name in folded for name in ("password=", "passwd=", "token=", "secret=")):
            safe.append("[REDACTED_ARGUMENT]")
            redactions["sensitive_process_argument"] += 1
            continue
        if token.startswith("--app=http://") or token.startswith("--app=https://"):
            prefix, raw_url = token.split("=", 1)
            sanitized_url = raw_url.split("?", 1)[0].split("#", 1)[0]
            safe.append(f"{prefix}={sanitized_url}")
            if sanitized_url != raw_url:
                redactions["url_query_or_fragment"] += 1
            continue
        safe.append(token)
    return " ".join(safe)[:800]


def sanitize_runtime_value(
    value: Any,
    redactions: Counter[str],
    *,
    key: str = "",
) -> Any:
    """Recursively sanitize runtime events before exporting the shareable package."""

    folded_key = key.casefold()
    if any(
        term in folded_key
        for term in (
            "password", "passwd", "secret", "token", "clipboard", "content",
            "message_text",
        )
    ):
        redactions[f"runtime_field:{folded_key}"] += 1
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_runtime_value(
                child_value, redactions, key=str(child_key)
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_runtime_value(item, redactions, key=key) for item in value]
    if isinstance(value, str):
        if folded_key in {"title", "window_title"}:
            return sanitized_window_title(value, redactions)
        if folded_key in {"url", "target"} and value.startswith(("http://", "https://")):
            sanitized = value.split("?", 1)[0].split("#", 1)[0]
            if sanitized != value:
                redactions["runtime_url_query_or_fragment"] += 1
            return sanitized
        if folded_key in {"arguments", "command_line"}:
            return sanitized_arguments(value, redactions)
    return value


def parse_xinput_keymap(output: str) -> dict[int, str]:
    """Return only a safe keycode-to-control-name map from ``xmodmap -pke``."""

    mapping: dict[int, str] = {}
    pattern = re.compile(r"^keycode\s+(\d+)\s*=\s*(.*)$")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match is None:
            continue
        keycode = int(match.group(1))
        names = [name for name in match.group(2).split() if name != "NoSymbol"]
        safe = next((name for name in names if name in _SPECIAL_KEY_NAMES), None)
        if safe is not None:
            mapping[keycode] = safe
    return mapping


def classify_key(keycode: int, safe_map: dict[int, str]) -> tuple[str, str | None]:
    name = safe_map.get(keycode)
    if name is None:
        return "text_key", None
    return "control_key", name


def parse_xinput_event_block(
    lines: list[str],
    *,
    safe_keymap: dict[int, str],
    pointer: dict[str, Any],
) -> dict[str, Any] | None:
    """Parse one XI2 event without retaining textual key contents."""

    if not lines:
        return None
    event_match = re.search(
        r"EVENT\s+type\s+\d+\s+\(([^)]+)\)", lines[0].strip()
    )
    if event_match is None:
        return None
    raw_type = event_match.group(1).strip()
    details: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.strip().split(":", 1)
        details[key.strip().casefold().replace(" ", "_")] = value.strip()
    try:
        match = re.search(r"-?\d+", details.get("detail", ""))
        detail = int(match.group(0)) if match is not None else 0
    except ValueError:
        detail = 0
    payload: dict[str, Any] = {
        "raw_event_type": raw_type,
        "pointer_x": pointer.get("x"),
        "pointer_y": pointer.get("y"),
        "window_under_pointer": pointer.get("window"),
    }
    folded = raw_type.casefold()
    if "key" in folded:
        category, safe_name = classify_key(detail, safe_keymap)
        payload.update(
            input_category=category,
            key_name=safe_name,
            pressed="press" in folded,
            literal_text_captured=False,
        )
        return payload
    if "button" in folded:
        payload.update(
            input_category="mouse_button",
            button=detail,
            pressed="press" in folded,
        )
        if detail in (4, 5, 6, 7):
            payload["input_category"] = "mouse_wheel"
            payload["scroll_direction"] = {
                4: "up", 5: "down", 6: "left", 7: "right"
            }.get(detail)
        return payload
    if "motion" in folded:
        payload["input_category"] = "pointer_motion"
        return payload
    return None


def command_output(command: list[str], timeout: float = 3.0) -> tuple[int, str, str]:
    executable = shutil.which(command[0])
    if executable is None:
        return 127, "", f"{command[0]} not found"
    try:
        result = subprocess.run(
            [executable, *command[1:]],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 126, "", str(exc)
    return result.returncode, result.stdout, result.stderr


def pointer_snapshot() -> dict[str, Any]:
    code, output, _error = command_output(["xdotool", "getmouselocation", "--shell"])
    if code != 0:
        return {}
    values: dict[str, Any] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().casefold()
        value = value.strip()
        if key in {"x", "y", "screen", "window"}:
            try:
                values[key] = int(value)
            except ValueError:
                values[key] = value
    return values


def window_identity(window_id: str, redactions: Counter[str]) -> dict[str, Any]:
    if not window_id:
        return {}
    _code, title, _error = command_output(["xdotool", "getwindowname", window_id])
    _code, window_class, _error = command_output(
        ["xdotool", "getwindowclassname", window_id]
    )
    _code, pid, _error = command_output(["xdotool", "getwindowpid", window_id])
    return {
        "window_id": window_id,
        "title": sanitized_window_title(title.strip(), redactions),
        "window_class": window_class.strip()[:160],
        "pid": int(pid.strip()) if pid.strip().isdigit() else None,
    }


def active_window_snapshot(redactions: Counter[str]) -> dict[str, Any]:
    code, output, _error = command_output(["xdotool", "getactivewindow"])
    if code != 0:
        return {}
    return window_identity(output.strip(), redactions)


def relevant_processes(redactions: Counter[str]) -> dict[int, tuple[object, ...]]:
    code, output, _error = command_output(
        ["ps", "-eo", "pid=,ppid=,pgid=,etimes=,comm=,args="], timeout=8
    )
    if code != 0:
        return {}
    snapshot: dict[int, tuple[object, ...]] = {}
    pattern = re.compile(
        r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(.*)$"
    )
    for line in output.splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        pid, ppid, pgid, elapsed, command, arguments = match.groups()
        folded = arguments.casefold()
        if not any(
            token in folded
            for token in (
                "triview_workspace", "triview-workspace-candidates",
                "browser-profiles", "--class=triview-", "--name=triview-",
            )
        ):
            continue
        snapshot[int(pid)] = (
            int(ppid), int(pgid), int(elapsed), command,
            sanitized_arguments(arguments, redactions),
        )
    return snapshot


def parse_root_tree(
    output: str,
    redactions: Counter[str],
) -> dict[str, tuple[object, ...]]:
    snapshot: dict[str, tuple[object, ...]] = {}
    pattern = re.compile(
        r'^\s*(0x[0-9a-fA-F]+)\s+"([^"]*)".*?\s(\d+)x(\d+)\+(-?\d+)\+(-?\d+)'
    )
    for line in output.splitlines():
        match = pattern.search(line)
        if match is None:
            continue
        window_id, title, width, height, x, y = match.groups()
        folded = line.casefold()
        if not any(
            token in folded
            for token in ("triview", "brave", "chromium", '"tk"', "terminal")
        ):
            continue
        snapshot[window_id] = (
            sanitized_window_title(title, redactions),
            int(width), int(height), int(x), int(y),
        )
    return snapshot


def window_tree_snapshot(redactions: Counter[str]) -> dict[str, tuple[object, ...]]:
    code, output, _error = command_output(["xwininfo", "-root", "-tree"], timeout=8)
    if code != 0:
        return {}
    return parse_root_tree(output, redactions)


def safe_copy(source: Path, destination: Path) -> bool:
    try:
        if source.exists():
            shutil.copy2(source, destination)
            return True
    except OSError:
        return False
    return False


def create_paths(output_dir: Path, session_id: str) -> BlackboxPaths:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    root = output_dir / f"triview-blackbox-{stamp}-{session_id[:8]}"
    root.mkdir(parents=True, exist_ok=False)
    return BlackboxPaths(
        root=root,
        session_summary=root / "session-summary.json",
        timeline_html=root / "timeline.html",
        timeline_jsonl=root / "timeline.jsonl",
        user_input_events=root / "user-input-events.jsonl",
        system_events=root / "system-events.jsonl",
        triview_events=root / "triview-events.jsonl",
        x11_window_events=root / "x11-window-events.jsonl",
        process_events=root / "process-events.jsonl",
        runtime_provenance=root / "runtime-provenance.json",
        panel_runtime_inventory=root / "panel-runtime-inventory.json",
        errors=root / "errors.log",
        privacy_report=root / "privacy-redaction-report.json",
    )


class BlackboxCollector:
    """Collect user/system/runtime events only during one explicit session."""

    def __init__(
        self,
        output_dir: Path,
        timeout_seconds: int,
        *,
        auto_launch: bool = False,
        auto_stop_on_application_exit: bool = False,
    ) -> None:
        session_id = str(uuid.uuid4())
        self.paths = create_paths(output_dir, session_id)
        self.state = CollectorState(
            session_id=session_id,
            started_wall=utc_now(),
            started_monotonic_ns=time.monotonic_ns(),
        )
        self.timeout_seconds = max(30, int(timeout_seconds))
        self.auto_launch = bool(auto_launch)
        self.auto_stop_on_application_exit = bool(auto_stop_on_application_exit)
        self.launched_process: subprocess.Popen[bytes] | None = None
        self.stop_event = threading.Event()
        self.queue: queue.SimpleQueue[tuple[str, dict[str, Any]]] = queue.SimpleQueue()
        self.threads: list[threading.Thread] = []
        self.xinput_process: subprocess.Popen[str] | None = None
        self.runtime_events_path = state_root() / "runtime-events.jsonl"
        self.runtime_start_offset = (
            self.runtime_events_path.stat().st_size
            if self.runtime_events_path.exists()
            else 0
        )
        self.safe_keymap = self._load_safe_keymap()
        self.writers = {
            "timeline": self._writer(self.paths.timeline_jsonl),
            "user": self._writer(self.paths.user_input_events),
            "system": self._writer(self.paths.system_events),
            "triview": self._writer(self.paths.triview_events),
            "x11": self._writer(self.paths.x11_window_events),
            "process": self._writer(self.paths.process_events),
        }
        self._copy_initial_provenance()

    @staticmethod
    def _writer(path: Path) -> StreamWriter:
        return StreamWriter(path, path.open("w", encoding="utf-8"))

    def _load_safe_keymap(self) -> dict[int, str]:
        code, output, error = command_output(["xmodmap", "-pke"])
        if code != 0:
            self.state.errors.append(f"xmodmap unavailable: {error}")
            return {}
        return parse_xinput_keymap(output)

    def _copy_initial_provenance(self) -> None:
        source = state_root() / "runtime-provenance.json"
        if not safe_copy(source, self.paths.runtime_provenance):
            self.paths.runtime_provenance.write_text(
                json.dumps(runtime_identity(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    def start(self) -> None:
        self.emit(
            "system",
            {
                **event_base(self.state.session_id, "diagnostic", "blackbox_started"),
                "timeout_seconds": self.timeout_seconds,
                "runtime_events_start_offset": self.runtime_start_offset,
                "privacy_mode": "sanitized",
            },
        )
        for name, target in (
            ("pointer-active", self._pointer_active_loop),
            ("processes", self._process_loop),
            ("x11-windows", self._window_loop),
            ("runtime-events", self._runtime_event_loop),
            ("xinput", self._xinput_loop),
        ):
            thread = threading.Thread(
                target=self._guarded_thread,
                args=(name, target),
                name=f"triview-blackbox-{name}",
                daemon=True,
            )
            self.threads.append(thread)
            thread.start()

    def _guarded_thread(self, name: str, target: Any) -> None:
        try:
            target()
        except Exception as exc:  # noqa: BLE001
            message = f"{name}: {type(exc).__name__}: {exc}"
            self.state.errors.append(message)
            self.emit(
                "system",
                {
                    **event_base(self.state.session_id, "diagnostic", "collector_error"),
                    "collector": name,
                    "error": message,
                },
            )

    def emit(self, stream: str, payload: dict[str, Any]) -> None:
        self.queue.put((stream, payload))

    def drain(self) -> None:
        while True:
            try:
                stream, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            self._write_event(stream, payload)

    def _write_event(self, stream: str, payload: dict[str, Any]) -> None:
        writer = self.writers.get(stream, self.writers["system"])
        writer.write(payload)
        self.writers["timeline"].write(payload)
        event_type = str(payload.get("event_type") or payload.get("event") or "unknown")
        self.state.counts[f"{stream}:{event_type}"] += 1

    def _pointer_active_loop(self) -> None:
        while not self.stop_event.wait(POLL_INTERVAL_SECONDS):
            pointer = pointer_snapshot()
            active = active_window_snapshot(self.state.redactions)
            pointer_identity = window_identity(
                str(pointer.get("window", "")), self.state.redactions
            )
            pointer_signature = (
                pointer.get("x"), pointer.get("y"), pointer.get("window"),
                pointer_identity.get("window_class"),
            )
            if pointer_signature != self.state.last_pointer_signature:
                self.state.last_pointer_signature = pointer_signature
                self.emit(
                    "system",
                    {
                        **event_base(
                            self.state.session_id, "system", "pointer_context_changed"
                        ),
                        **pointer,
                        "window_under_pointer_identity": pointer_identity,
                    },
                )
            active_signature = tuple(
                active.get(key) for key in ("window_id", "pid", "title")
            )
            if active_signature != self.state.last_active_signature:
                self.state.last_active_signature = active_signature
                self.emit(
                    "system",
                    {
                        **event_base(
                            self.state.session_id, "system", "active_window_changed"
                        ),
                        "active_window": active,
                    },
                )

    def _process_loop(self) -> None:
        while not self.stop_event.wait(PROCESS_INTERVAL_SECONDS):
            current = relevant_processes(self.state.redactions)
            previous = self.state.last_process_snapshot
            for pid in sorted(set(current) - set(previous)):
                ppid, pgid, elapsed, command, arguments = current[pid]
                self.emit(
                    "process",
                    {
                        **event_base(
                            self.state.session_id, "system", "process_started_observed"
                        ),
                        "pid": pid, "ppid": ppid, "pgid": pgid,
                        "elapsed_seconds": elapsed, "command": command,
                        "arguments": arguments,
                    },
                )
            for pid in sorted(set(previous) - set(current)):
                ppid, pgid, _elapsed, command, arguments = previous[pid]
                self.emit(
                    "process",
                    {
                        **event_base(
                            self.state.session_id, "system", "process_stopped_observed"
                        ),
                        "pid": pid, "ppid": ppid, "pgid": pgid,
                        "command": command, "arguments": arguments,
                    },
                )
            self.state.last_process_snapshot = current

    def _window_loop(self) -> None:
        while not self.stop_event.wait(WINDOW_INTERVAL_SECONDS):
            current = window_tree_snapshot(self.state.redactions)
            previous = self.state.last_window_snapshot
            for window_id in sorted(set(current) - set(previous)):
                title, width, height, x, y = current[window_id]
                self.emit(
                    "x11",
                    {
                        **event_base(
                            self.state.session_id, "x11", "window_created_observed"
                        ),
                        "window_id": window_id, "title": title, "width": width,
                        "height": height, "x": x, "y": y,
                        "externally_visible_candidate": x >= 0 and y >= 0,
                    },
                )
            for window_id in sorted(set(previous) - set(current)):
                title, width, height, x, y = previous[window_id]
                self.emit(
                    "x11",
                    {
                        **event_base(
                            self.state.session_id, "x11", "window_destroyed_observed"
                        ),
                        "window_id": window_id, "title": title, "width": width,
                        "height": height, "x": x, "y": y,
                    },
                )
            for window_id in sorted(set(current) & set(previous)):
                if current[window_id] == previous[window_id]:
                    continue
                old, new = previous[window_id], current[window_id]
                self.emit(
                    "x11",
                    {
                        **event_base(
                            self.state.session_id, "x11", "window_geometry_changed"
                        ),
                        "window_id": window_id, "title": new[0],
                        "from": {
                            "width": old[1], "height": old[2], "x": old[3], "y": old[4]
                        },
                        "to": {
                            "width": new[1], "height": new[2], "x": new[3], "y": new[4]
                        },
                    },
                )
            self.state.last_window_snapshot = current

    def _runtime_event_loop(self) -> None:
        offset = self.runtime_start_offset
        while not self.stop_event.wait(0.15):
            if not self.runtime_events_path.exists():
                continue
            try:
                size = self.runtime_events_path.stat().st_size
                if size < offset:
                    offset = 0
                if size == offset:
                    continue
                with self.runtime_events_path.open("r", encoding="utf-8") as handle:
                    handle.seek(offset)
                    for line in handle:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            original = json.loads(stripped)
                        except json.JSONDecodeError:
                            self.state.errors.append("invalid runtime event JSON line")
                            continue
                        original = sanitize_runtime_value(
                            original, self.state.redactions
                        )
                        payload = {
                            **event_base(
                                self.state.session_id,
                                "triview",
                                str(original.get("event", "runtime_event")),
                            ),
                            "runtime_event": original,
                        }
                        self.emit("triview", payload)
                        if (
                            self.auto_stop_on_application_exit
                            and original.get("event") == "application_stopped"
                            and (
                                not original.get("diagnostic_session_id")
                                or original.get("diagnostic_session_id")
                                == self.state.session_id
                            )
                        ):
                            self.request_stop("application_stopped")
                    offset = handle.tell()
            except OSError as exc:
                self.state.errors.append(f"runtime event reader: {exc}")

    def _xinput_loop(self) -> None:
        executable = shutil.which("xinput")
        if executable is None or not os.environ.get("DISPLAY"):
            self.state.errors.append("xinput unavailable; user input events not captured")
            self.emit(
                "system",
                {
                    **event_base(
                        self.state.session_id, "diagnostic", "collector_unavailable"
                    ),
                    "collector": "xinput",
                    "reason": "xinput or DISPLAY unavailable",
                },
            )
            return
        self.xinput_process = subprocess.Popen(  # noqa: S603
            [executable, "test-xi2", "--root"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        assert self.xinput_process.stdout is not None
        block: list[str] = []
        for line in self.xinput_process.stdout:
            if self.stop_event.is_set():
                break
            if line.lstrip().startswith("EVENT type"):
                if block:
                    self._emit_xinput_block(block)
                block = [line]
            elif block:
                block.append(line)
        if block:
            self._emit_xinput_block(block)

    def _emit_xinput_block(self, block: list[str]) -> None:
        parsed = parse_xinput_event_block(
            block,
            safe_keymap=self.safe_keymap,
            pointer=pointer_snapshot(),
        )
        if parsed is None or parsed.get("input_category") == "pointer_motion":
            return
        if parsed.get("input_category") == "text_key":
            self.state.redactions["literal_keyboard_key"] += 1
        self.emit(
            "user",
            {
                **event_base(
                    self.state.session_id, "user_input", "user_input_observed"
                ),
                **parsed,
            },
        )

    def launch_triview(self) -> None:
        """Launch the candidate after collectors are active, without closing work."""

        if not self.auto_launch or self.stop_event.is_set():
            return
        app_root = os.environ.get("TRIVIEW_APP_ROOT")
        data_root = os.environ.get("XDG_DATA_HOME")
        state_home = os.environ.get("XDG_STATE_HOME")
        module = os.environ.get("TRIVIEW_RUNTIME_MODULE", "triview_workspace.gui")
        script = runtime_root() / "scripts" / "candidate-launch.sh"
        if not app_root or not data_root or not state_home or not script.is_file():
            self.state.errors.append("auto-launch unavailable: candidate environment incomplete")
            self.emit(
                "system",
                {
                    **event_base(
                        self.state.session_id, "diagnostic", "auto_launch_unavailable"
                    ),
                    "script": str(script),
                },
            )
            return
        child_env = os.environ.copy()
        child_env["TRIVIEW_DIAGNOSTIC_SESSION_ID"] = self.state.session_id
        try:
            self.launched_process = subprocess.Popen(  # noqa: S603
                [
                    shutil.which("bash") or "/bin/bash",
                    str(script), app_root, data_root, state_home, module,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(runtime_root()),
                env=child_env,
                start_new_session=True,
            )
        except OSError as exc:
            self.state.errors.append(f"auto-launch failed: {exc}")
            self.emit(
                "system",
                {
                    **event_base(
                        self.state.session_id, "diagnostic", "auto_launch_failed"
                    ),
                    "error": str(exc),
                },
            )
            return
        self.emit(
            "system",
            {
                **event_base(self.state.session_id, "diagnostic", "auto_launch_started"),
                "launcher_pid": self.launched_process.pid,
                "runtime_module": module,
            },
        )

    def request_stop(self, reason: str) -> None:
        if self.stop_event.is_set():
            return
        self.state.stop_reason = reason
        self.stop_event.set()
        if self.xinput_process is not None and self.xinput_process.poll() is None:
            self.xinput_process.terminate()

    def finalize(self) -> Path:
        self.request_stop(self.state.stop_reason)
        for thread in self.threads:
            thread.join(timeout=1.5)
        self.drain()
        stopped_wall = utc_now()
        stopped_monotonic_ns = time.monotonic_ns()
        self._write_event(
            "system",
            {
                **event_base(self.state.session_id, "diagnostic", "blackbox_stopped"),
                "reason": self.state.stop_reason,
            },
        )
        for writer in self.writers.values():
            writer.close()
        self._write_inventory()
        self._write_privacy_report()
        self._write_errors()
        self._write_summary(stopped_wall, stopped_monotonic_ns)
        self._write_timeline_html()
        package = self.paths.root.with_suffix(".zip")
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(self.paths.root.iterdir()):
                archive.write(path, arcname=path.name)
        return package

    def _write_inventory(self) -> None:
        current_processes = relevant_processes(self.state.redactions)
        current_windows = window_tree_snapshot(self.state.redactions)
        runtime_events = self._read_jsonl(self.paths.triview_events)
        latest_runtime_by_id: dict[str, dict[str, Any]] = {}
        for wrapped in runtime_events:
            original = wrapped.get("runtime_event", {})
            runtime_id = original.get("runtime_id") or original.get("panel_id")
            if runtime_id:
                latest_runtime_by_id[str(runtime_id)] = original
        payload = {
            "session_id": self.state.session_id,
            "generated_at": utc_now(),
            "processes": [
                {
                    "pid": pid, "ppid": values[0], "pgid": values[1],
                    "elapsed_seconds": values[2], "command": values[3],
                    "arguments": values[4],
                }
                for pid, values in sorted(current_processes.items())
            ],
            "windows": [
                {
                    "window_id": window_id, "title": values[0],
                    "width": values[1], "height": values[2],
                    "x": values[3], "y": values[4],
                }
                for window_id, values in sorted(current_windows.items())
            ],
            "latest_runtime_events": latest_runtime_by_id,
        }
        self.paths.panel_runtime_inventory.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_privacy_report(self) -> None:
        payload = {
            "session_id": self.state.session_id,
            "generated_at": utc_now(),
            "mode": "sanitized",
            "literal_text_captured": False,
            "password_fields_captured": False,
            "clipboard_captured": False,
            "screenshots_captured": False,
            "audio_captured": False,
            "redaction_counts": dict(self.state.redactions),
            "rules": [
                "ordinary keyboard keys are stored only as text_key",
                "only named control keys are retained",
                "sensitive-looking window titles are redacted",
                "no clipboard, screenshots, audio, passwords or literal text are collected",
            ],
        }
        self.paths.privacy_report.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _write_errors(self) -> None:
        self.paths.errors.write_text(
            "\n".join(self.state.errors).rstrip()
            + ("\n" if self.state.errors else ""),
            encoding="utf-8",
        )

    def _write_summary(self, stopped_wall: str, stopped_monotonic_ns: int) -> None:
        runtime_events = self._read_jsonl(self.paths.triview_events)
        input_events = self._read_jsonl(self.paths.user_input_events)
        metadata = load_candidate_metadata()
        payload = {
            "schema_version": 1,
            "session_id": self.state.session_id,
            "started_at": self.state.started_wall,
            "stopped_at": stopped_wall,
            "duration_seconds": round(
                (stopped_monotonic_ns - self.state.started_monotonic_ns)
                / 1_000_000_000,
                3,
            ),
            "stop_reason": self.state.stop_reason,
            "runtime_sha": os.environ.get("TRIVIEW_RUNTIME_SHA")
            or metadata.get("resolved_sha"),
            "runtime_module": os.environ.get("TRIVIEW_RUNTIME_MODULE")
            or metadata.get("module"),
            "counts": dict(self.state.counts),
            "collectors": {
                "xinput": shutil.which("xinput") is not None,
                "xdotool": shutil.which("xdotool") is not None,
                "xwininfo": shutil.which("xwininfo") is not None,
                "ps": shutil.which("ps") is not None,
            },
            "privacy": {
                "literal_text_captured": False,
                "passwords_captured": False,
                "screenshots_captured": False,
            },
            "findings": self._derive_findings(runtime_events, input_events),
            "errors": self.state.errors,
            "stream_truncation": {
                name: writer.truncated for name, writer in self.writers.items()
            },
        }
        self.paths.session_summary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(payload, dict):
                        records.append(payload)
        except OSError:
            pass
        return records

    @staticmethod
    def _derive_findings(
        wrapped_runtime_events: list[dict[str, Any]],
        input_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        originals = [event.get("runtime_event", {}) for event in wrapped_runtime_events]
        names = [str(event.get("event", "")) for event in originals]
        delivered_values = [
            bool(event.get("delivered"))
            for event in originals
            if event.get("event") == "mouse_wheel_delivered"
        ]
        parked = [
            event for event in originals
            if event.get("event") == "workspace_view_parked"
        ]
        restored = [
            event for event in originals
            if event.get("event") == "workspace_view_restored"
        ]
        hidden_staging = [
            event for event in originals
            if event.get("event") == "browser_window_hidden_staging"
        ]
        visible_before = any(
            bool(event.get("visible_before")) for event in hidden_staging
        )
        return {
            "scroll": {
                "system_wheel_events": sum(
                    event.get("input_category") == "mouse_wheel"
                    for event in input_events
                ),
                "triview_received": sum(
                    name == "mouse_wheel_received" for name in names
                ),
                "delivered_attempts": len(delivered_values),
                "all_delivered": bool(delivered_values) and all(delivered_values),
            },
            "workspace_continuity": {
                "park_events": len(parked),
                "restore_events": len(restored),
                "destroyed_during_park": sum(
                    int(event.get("destroyed_runtimes", 0) or 0)
                    for event in parked
                ),
                "runtime_ids_restored": [
                    event.get("runtime_ids", []) for event in restored
                ],
            },
            "external_exposure": {
                "hidden_staging_events": len(hidden_staging),
                "visible_before_staging": visible_before,
                "provisional_pass": bool(hidden_staging) and not visible_before,
            },
        }

    def _write_timeline_html(self) -> None:
        records = self._read_jsonl(self.paths.timeline_jsonl)
        records.sort(key=lambda item: int(item.get("monotonic_ns", 0) or 0))
        rows: list[str] = []
        for record in records:
            details = {
                key: value
                for key, value in record.items()
                if key not in {"timestamp", "monotonic_ns", "source", "event_type"}
            }
            rows.append(
                "<tr>"
                f"<td>{html.escape(str(record.get('timestamp', '')))}</td>"
                f"<td>{html.escape(str(record.get('source', '')))}</td>"
                f"<td>{html.escape(str(record.get('event_type', '')))}</td>"
                f"<td><pre>{html.escape(json.dumps(details, ensure_ascii=False, indent=2, default=str))}</pre></td>"
                "</tr>"
            )
        page = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>TriView — Linha do tempo técnica</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#0f172a;color:#e2e8f0}}
h1{{font-size:22px}}p{{color:#94a3b8}}table{{width:100%;border-collapse:collapse}}
th,td{{border:1px solid #334155;padding:8px;vertical-align:top;text-align:left}}
th{{position:sticky;top:0;background:#1e293b}}pre{{white-space:pre-wrap;margin:0;font-size:12px}}
</style></head><body>
<h1>TriView — Linha do tempo técnica</h1>
<p>Sessão {html.escape(self.state.session_id)}. Conteúdo digitado, senhas, clipboard, áudio e imagens não foram coletados.</p>
<table><thead><tr><th>Horário</th><th>Origem</th><th>Evento</th><th>Detalhes</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></body></html>"""
        self.paths.timeline_html.write_text(page, encoding="utf-8")


class DiagnosticWindow:
    """Visible controller for one explicit black-box session."""

    def __init__(self, collector: BlackboxCollector) -> None:
        self.collector = collector
        self.root = tk.Tk()
        self.root.title("TriView — Diagnóstico caixa-preta ativo")
        self.root.geometry("520x230+40+40")
        self.root.minsize(480, 210)
        self.root.configure(background="#0f172a")
        self.root.protocol("WM_DELETE_WINDOW", self._stop)
        self.started = time.monotonic()
        self.remaining = tk.StringVar()
        self.status = tk.StringVar(value="Coletando eventos técnicos sanitizados…")
        tk.Label(
            self.root,
            text="● DIAGNÓSTICO ATIVO",
            background="#0f172a",
            foreground="#f87171",
            font=("Sans", 14, "bold"),
        ).pack(pady=(20, 8))
        tk.Label(
            self.root,
            text=(
                "Reproduza o problema no TriView. Esta sessão registra cliques, scroll, "
                "teclas de controle, foco, processos, janelas X11 e eventos internos.\n"
                "Textos, senhas, clipboard, áudio e imagens não são coletados."
            ),
            background="#0f172a",
            foreground="#cbd5e1",
            wraplength=470,
            justify="center",
        ).pack(padx=18)
        tk.Label(
            self.root,
            textvariable=self.remaining,
            background="#0f172a",
            foreground="#94a3b8",
            font=("Sans", 9),
        ).pack(pady=(10, 2))
        tk.Label(
            self.root,
            textvariable=self.status,
            background="#0f172a",
            foreground="#94a3b8",
            font=("Sans", 9),
        ).pack()
        tk.Button(
            self.root,
            text="Encerrar e gerar pacote",
            command=self._stop,
            background="#dc2626",
            foreground="white",
            activebackground="#b91c1c",
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=8,
        ).pack(pady=14)
        self.root.bind(
            "<Control-Shift-Escape>", lambda _event: self._stop("shortcut")
        )
        self.root.after(100, self._tick)
        if self.collector.auto_launch:
            self.root.after(500, self.collector.launch_triview)

    def _tick(self) -> None:
        self.collector.drain()
        elapsed = time.monotonic() - self.started
        remaining = max(0, self.collector.timeout_seconds - int(elapsed))
        self.remaining.set(
            f"Encerramento automático em {remaining // 60:02d}:{remaining % 60:02d}"
        )
        if elapsed >= self.collector.timeout_seconds:
            self._stop("timeout")
            return
        if self.collector.stop_event.is_set():
            self.status.set("Aplicação encerrada; gerando o pacote…")
            self.root.after(50, self.root.quit)
            return
        self.root.after(100, self._tick)

    def _stop(self, reason: str = "user_requested") -> None:
        if self.collector.stop_event.is_set():
            return
        self.status.set("Finalizando coletores e gerando o pacote…")
        self.collector.request_stop(reason)
        self.root.after(50, self.root.quit)

    def run(self) -> None:
        self.collector.start()
        self.root.mainloop()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def run_blackbox(
    output_dir: Path,
    timeout_seconds: int,
    *,
    auto_launch: bool = False,
    auto_stop_on_application_exit: bool = False,
) -> Path:
    collector = BlackboxCollector(
        output_dir,
        timeout_seconds,
        auto_launch=auto_launch,
        auto_stop_on_application_exit=auto_stop_on_application_exit,
    )
    window = DiagnosticWindow(collector)
    window.run()
    return collector.finalize()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sessão explícita de diagnóstico caixa-preta do TriView"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS
    )
    parser.add_argument("--auto-launch", action="store_true")
    parser.add_argument("--auto-stop-on-application-exit", action="store_true")
    arguments = parser.parse_args(argv)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    package = run_blackbox(
        arguments.output_dir,
        arguments.timeout_seconds,
        auto_launch=arguments.auto_launch,
        auto_stop_on_application_exit=arguments.auto_stop_on_application_exit,
    )
    print(package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
