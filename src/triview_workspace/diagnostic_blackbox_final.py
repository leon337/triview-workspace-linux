"""Final privacy and evidence hardening for the TriView black-box package."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from triview_workspace.diagnostic_blackbox import (
    DEFAULT_TIMEOUT_SECONDS,
    DiagnosticWindow,
    command_output,
    event_base,
    sanitized_window_title,
)
from triview_workspace.diagnostic_blackbox_rc import ByteSafeBlackboxCollector

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|token|secret|authorization|cookie)=([^\s]+)"
)
_URL_PATTERN = re.compile(r"https?://[^\s\]\[\"'<>]+")
_HOME_PATH_PATTERN = re.compile(r"/(?:home|Users)/[^/\s]+/[^\s]*")
_RUNTIME_SECRET_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "clipboard",
    "content",
    "message_text",
    "body_text",
    "typed_text",
)
_SAFE_FLAGS = (
    "--type=",
    "--class=",
    "--name=",
    "--window-position=",
    "--window-size=",
    "--ozone-platform=",
    "--lang=",
    "--service-sandbox-type=",
)
_SAFE_SWITCHES = {
    "--no-first-run",
    "--no-default-browser-check",
    "--start-minimized",
    "--enable-main-frame-before-activation",
}


def sanitize_url_origin(value: str) -> str:
    """Reduce one HTTP URL to scheme, host and optional non-default port."""

    try:
        parsed = urlsplit(value)
    except ValueError:
        return "[REDACTED_URL]"
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "[REDACTED_URL]"
    host = parsed.hostname.casefold()
    port = parsed.port
    default_port = 80 if parsed.scheme == "http" else 443
    authority = host if port in (None, default_port) else f"{host}:{port}"
    return f"{parsed.scheme}://{authority}/"


def sanitize_generic_string(value: str, redactions: dict[str, int] | Any) -> str:
    """Remove secrets, private URL paths and user-home paths from free text."""

    sanitized = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    if sanitized != value:
        redactions["secret_assignment"] += 1
    replaced_urls = 0

    def replace_url(match: re.Match[str]) -> str:
        nonlocal replaced_urls
        replaced_urls += 1
        return sanitize_url_origin(match.group(0))

    sanitized = _URL_PATTERN.sub(replace_url, sanitized)
    if replaced_urls:
        redactions["url_reduced_to_origin"] += replaced_urls
    sanitized, home_replacements = _HOME_PATH_PATTERN.subn("[LOCAL_PATH]", sanitized)
    if home_replacements:
        redactions["home_path"] += home_replacements
    return sanitized[:1000]


def strict_sanitized_arguments(arguments: str, redactions: Any) -> str:
    """Export only process role, safe flags and URL origins."""

    try:
        tokens = shlex.split(arguments)
    except ValueError:
        tokens = arguments.split()
    if not tokens:
        return ""
    safe: list[str] = [Path(tokens[0]).name]
    preserve_next_module = False
    for token in tokens[1:120]:
        folded = token.casefold()
        if preserve_next_module:
            safe.append(token if token.startswith("triview_workspace.") else "[MODULE]")
            preserve_next_module = False
            continue
        if token == "-m":
            safe.append(token)
            preserve_next_module = True
            continue
        if token in _SAFE_SWITCHES or token.startswith(_SAFE_FLAGS):
            safe.append(token)
            continue
        if folded.startswith("--app="):
            raw_url = token.split("=", 1)[1]
            safe.append(f"--app={sanitize_url_origin(raw_url)}")
            redactions["process_app_url_path"] += 1
            continue
        if folded.startswith("--user-data-dir="):
            safe.append("--user-data-dir=[PROFILE_DIR]")
            redactions["profile_directory"] += 1
            continue
        if _SECRET_ASSIGNMENT.search(token):
            safe.append("[REDACTED_ARGUMENT]")
            redactions["sensitive_process_argument"] += 1
            continue
        if token.startswith(("http://", "https://")):
            safe.append(sanitize_url_origin(token))
            redactions["process_url_path"] += 1
            continue
        safe.append("[ARG]")
        redactions["nonessential_process_argument"] += 1
    return " ".join(safe)[:800]


def strict_sanitize_runtime_value(
    value: Any,
    redactions: Any,
    *,
    key: str = "",
) -> Any:
    """Recursively enforce origin-only URLs and deny-by-default text export."""

    folded_key = key.casefold()
    if any(term in folded_key for term in _RUNTIME_SECRET_KEYS):
        redactions[f"runtime_field:{folded_key}"] += 1
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(child_key): strict_sanitize_runtime_value(
                child_value,
                redactions,
                key=str(child_key),
            )
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        if folded_key in {"command", "argv", "arguments_list"}:
            joined = " ".join(str(item) for item in value)
            return strict_sanitized_arguments(joined, redactions).split()
        return [strict_sanitize_runtime_value(item, redactions, key=key) for item in value]
    if not isinstance(value, str):
        return value
    if folded_key in {"title", "window_title"}:
        return sanitized_window_title(value, redactions)
    if folded_key in {"url", "target"}:
        if value.startswith(("http://", "https://")):
            redactions["runtime_url_path"] += 1
            return sanitize_url_origin(value)
        if value.startswith(("file://", "/")):
            redactions["runtime_local_target"] += 1
            return "[LOCAL_RESOURCE]"
    if folded_key in {"arguments", "command_line"}:
        return strict_sanitized_arguments(value, redactions)
    if folded_key.endswith("_path") or folded_key.endswith("_dir"):
        redactions["runtime_local_path"] += 1
        return f"[LOCAL_PATH]/{Path(value).name}" if value else "[LOCAL_PATH]"
    return sanitize_generic_string(value, redactions)


def strict_relevant_processes(redactions: Any) -> dict[int, tuple[object, ...]]:
    code, output, _error = command_output(
        ["ps", "-eo", "pid=,ppid=,pgid=,etimes=,comm=,args="],
        timeout=8,
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
                "triview_workspace",
                "triview-workspace-candidates",
                "browser-profiles",
                "--class=triview-",
                "--name=triview-",
            )
        ):
            continue
        snapshot[int(pid)] = (
            int(ppid),
            int(pgid),
            int(elapsed),
            Path(command).name,
            strict_sanitized_arguments(arguments, redactions),
        )
    return snapshot


def normalize_window_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value), 0)
    except ValueError:
        try:
            return int(str(value), 10)
        except ValueError:
            return None


class FinalBlackboxCollector(ByteSafeBlackboxCollector):
    """Generate privacy-strict findings that cannot silently overstate PASS."""

    def _emit_runtime_line(self, raw_line: bytes) -> None:
        try:
            original = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.state.errors.append("invalid runtime event JSON line")
            return
        if not isinstance(original, dict):
            return
        sanitized = strict_sanitize_runtime_value(original, self.state.redactions)
        payload = {
            **event_base(
                self.state.session_id,
                "triview",
                str(sanitized.get("event", "runtime_event")),
            ),
            "runtime_event": sanitized,
        }
        self.emit("triview", payload)
        if (
            self.auto_stop_on_application_exit
            and sanitized.get("event") == "application_stopped"
            and (
                not sanitized.get("diagnostic_session_id")
                or sanitized.get("diagnostic_session_id") == self.state.session_id
            )
        ):
            self.request_stop("application_stopped")

    def _process_loop(self) -> None:
        while not self.stop_event.wait(1.0):
            current = strict_relevant_processes(self.state.redactions)
            previous = self.state.last_process_snapshot
            for pid in sorted(set(current) - set(previous)):
                ppid, pgid, elapsed, command, arguments = current[pid]
                self.emit(
                    "process",
                    {
                        **event_base(
                            self.state.session_id,
                            "system",
                            "process_started_observed",
                        ),
                        "pid": pid,
                        "ppid": ppid,
                        "pgid": pgid,
                        "elapsed_seconds": elapsed,
                        "command": command,
                        "arguments": arguments,
                    },
                )
            for pid in sorted(set(previous) - set(current)):
                ppid, pgid, _elapsed, command, arguments = previous[pid]
                self.emit(
                    "process",
                    {
                        **event_base(
                            self.state.session_id,
                            "system",
                            "process_stopped_observed",
                        ),
                        "pid": pid,
                        "ppid": ppid,
                        "pgid": pgid,
                        "command": command,
                        "arguments": arguments,
                    },
                )
            self.state.last_process_snapshot = current

    def _write_inventory(self) -> None:
        current_processes = strict_relevant_processes(self.state.redactions)
        runtime_events = self._read_jsonl(self.paths.triview_events)
        latest_runtime_by_id: dict[str, dict[str, Any]] = {}
        for wrapped in runtime_events:
            original = wrapped.get("runtime_event", {})
            runtime_id = original.get("runtime_id") or original.get("panel_id")
            if runtime_id:
                latest_runtime_by_id[str(runtime_id)] = original
        payload = {
            "session_id": self.state.session_id,
            "generated_at": event_base(
                self.state.session_id,
                "diagnostic",
                "inventory_generated",
            )["timestamp"],
            "processes": [
                {
                    "pid": pid,
                    "ppid": values[0],
                    "pgid": values[1],
                    "elapsed_seconds": values[2],
                    "command": values[3],
                    "arguments": values[4],
                }
                for pid, values in sorted(current_processes.items())
            ],
            "latest_runtime_events": latest_runtime_by_id,
        }
        self.paths.panel_runtime_inventory.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _derive_findings(
        self,
        wrapped_runtime_events: list[dict[str, Any]],
        input_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        runtime_records = [
            (wrapped, wrapped.get("runtime_event", {}))
            for wrapped in wrapped_runtime_events
            if isinstance(wrapped.get("runtime_event", {}), dict)
        ]
        x11_events = self._read_jsonl(self.paths.x11_window_events)
        wheel_events = [
            event
            for event in input_events
            if event.get("input_category") == "mouse_wheel"
        ]
        wheel_deliveries = [
            original
            for _wrapped, original in runtime_records
            if original.get("event")
            in {"mouse_wheel_delivered", "wheel_event_forwarded"}
        ]
        delivery_failures = [
            event for event in wheel_deliveries if not bool(event.get("delivered"))
        ]
        if delivery_failures:
            scroll_status = "FAIL"
        elif wheel_events and wheel_deliveries:
            scroll_status = "PASS_TECHNICAL_ROUTE"
        elif wheel_events:
            scroll_status = "FAIL_NO_TRIVIEW_ROUTE"
        else:
            scroll_status = "INDETERMINATE_NO_WHEEL_EVENT"

        exposure = self._external_exposure_finding(runtime_records, x11_events)
        continuity = self._workspace_continuity_finding(runtime_records)
        return {
            "scroll": {
                "status": scroll_status,
                "system_wheel_events": len(wheel_events),
                "delivery_attempts": len(wheel_deliveries),
                "delivery_failures": len(delivery_failures),
                "requires_physical_page_confirmation": True,
            },
            "workspace_continuity": continuity,
            "external_exposure": exposure,
        }

    @staticmethod
    def _external_exposure_finding(
        runtime_records: list[tuple[dict[str, Any], dict[str, Any]]],
        x11_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        forced = [
            original
            for _wrapped, original in runtime_records
            if original.get("event") == "browser_candidate_forced_hidden"
        ]
        staging = [
            original
            for _wrapped, original in runtime_records
            if original.get("event") == "browser_window_hidden_staging"
        ]
        embedded_by_window: dict[int, int] = {}
        for wrapped, original in runtime_records:
            if original.get("event") != "browser_launch_embedded":
                continue
            window_id = normalize_window_id(original.get("browser_window_id"))
            if window_id is not None:
                embedded_by_window[window_id] = int(wrapped.get("monotonic_ns", 0) or 0)
        pre_embed_visible_windows: list[int] = []
        for event in x11_events:
            if event.get("event_type") != "window_created_observed":
                continue
            if not bool(event.get("externally_visible_candidate")):
                continue
            window_id = normalize_window_id(event.get("window_id"))
            if window_id is None or window_id not in embedded_by_window:
                continue
            if int(event.get("monotonic_ns", 0) or 0) < embedded_by_window[window_id]:
                pre_embed_visible_windows.append(window_id)
        visible_before_hide = [
            event for event in forced if bool(event.get("visible_before_hide"))
        ]
        visible_before_staging = [
            event for event in staging if bool(event.get("visible_before"))
        ]
        if visible_before_hide or visible_before_staging or pre_embed_visible_windows:
            status = "FAIL_EXTERNAL_VISIBILITY_BEFORE_EMBED"
        elif forced and staging and embedded_by_window:
            status = "PASS_TECHNICAL_NO_EXTERNAL_VISIBILITY"
        else:
            status = "INDETERMINATE_INSUFFICIENT_EVENTS"
        return {
            "status": status,
            "forced_hide_events": len(forced),
            "visible_before_hide": len(visible_before_hide),
            "visible_before_staging": len(visible_before_staging),
            "pre_embed_visible_window_ids": sorted(set(pre_embed_visible_windows)),
            "embedded_window_count": len(embedded_by_window),
        }

    @staticmethod
    def _workspace_continuity_finding(
        runtime_records: list[tuple[dict[str, Any], dict[str, Any]]],
    ) -> dict[str, Any]:
        snapshots: list[tuple[int, dict[str, Any]]] = [
            (int(wrapped.get("monotonic_ns", 0) or 0), original)
            for wrapped, original in runtime_records
            if original.get("event") == "workspace_runtime_snapshot"
        ]
        launches: list[tuple[int, str]] = [
            (
                int(wrapped.get("monotonic_ns", 0) or 0),
                str(original.get("panel_id", "")),
            )
            for wrapped, original in runtime_records
            if original.get("event") == "browser_launch_requested"
        ]
        parked_by_workspace: dict[str, tuple[int, dict[str, Any]]] = {}
        cycles: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        for timestamp, snapshot in sorted(snapshots, key=lambda item: item[0]):
            workspace_id = str(snapshot.get("workspace_id", ""))
            phase = snapshot.get("phase")
            if phase == "parked":
                parked_by_workspace[workspace_id] = (timestamp, snapshot)
                continue
            if phase != "restored" or workspace_id not in parked_by_workspace:
                continue
            parked_time, parked = parked_by_workspace[workspace_id]
            before = {
                str(item.get("runtime_id")): item
                for item in parked.get("runtimes", [])
                if item.get("runtime_id") and item.get("active")
            }
            after = {
                str(item.get("runtime_id")): item
                for item in snapshot.get("runtimes", [])
                if item.get("runtime_id") and item.get("active")
            }
            runtime_ids = sorted(set(before) | set(after))
            cycle_failures: list[dict[str, Any]] = []
            for runtime_id in runtime_ids:
                old = before.get(runtime_id)
                new = after.get(runtime_id)
                relaunches = sum(
                    parked_time < launch_time < timestamp and launched_id == runtime_id
                    for launch_time, launched_id in launches
                )
                same_pid = old is not None and new is not None and old.get("pid") == new.get("pid")
                same_window = (
                    old is not None
                    and new is not None
                    and old.get("window_id") == new.get("window_id")
                )
                if old is None or new is None or not same_pid or not same_window or relaunches:
                    cycle_failures.append(
                        {
                            "runtime_id": runtime_id,
                            "present_before": old is not None,
                            "present_after": new is not None,
                            "same_pid": same_pid,
                            "same_window_id": same_window,
                            "relaunches": relaunches,
                        }
                    )
            cycle = {
                "workspace_id": workspace_id,
                "runtime_ids": runtime_ids,
                "failures": cycle_failures,
            }
            cycles.append(cycle)
            failures.extend(cycle_failures)
        if failures:
            status = "FAIL_RUNTIME_CHANGED_OR_RELAUNCHED"
        elif cycles:
            status = "PASS_SAME_PID_AND_WINDOW_ID"
        else:
            status = "INDETERMINATE_NO_PARK_RESTORE_CYCLE"
        return {
            "status": status,
            "cycles": cycles,
            "failure_count": len(failures),
        }


def run_blackbox(
    output_dir: Path,
    timeout_seconds: int,
    *,
    auto_launch: bool = False,
    auto_stop_on_application_exit: bool = False,
) -> Path:
    collector = FinalBlackboxCollector(
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
        description="Diagnóstico caixa-preta final com privacidade por allowlist"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
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


__all__ = [
    "FinalBlackboxCollector",
    "main",
    "normalize_window_id",
    "run_blackbox",
    "sanitize_url_origin",
    "strict_relevant_processes",
    "strict_sanitize_runtime_value",
    "strict_sanitized_arguments",
]


if __name__ == "__main__":
    raise SystemExit(main())
