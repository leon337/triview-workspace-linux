"""Shareable TriView black-box package with strict privacy and exact findings."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from triview_workspace.diagnostic_blackbox import (
    DEFAULT_TIMEOUT_SECONDS,
    DiagnosticWindow,
    classify_key,
    event_base,
    pointer_snapshot,
    runtime_identity,
    state_root,
)
from triview_workspace.diagnostic_blackbox_final import (
    FinalBlackboxCollector,
    normalize_window_id,
    sanitize_generic_string,
    strict_sanitize_runtime_value,
)


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    match = re.search(r"-?\d+", str(value))
    if match is None:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def parse_shareable_xinput_event(
    lines: list[str],
    *,
    safe_keymap: dict[int, str],
    pointer: dict[str, Any],
) -> dict[str, Any] | None:
    """Parse one non-raw XI2 event and retain no literal keyboard symbol."""

    if not lines:
        return None
    event_match = re.search(r"EVENT\s+type\s+\d+\s+\(([^)]+)\)", lines[0].strip())
    if event_match is None:
        return None
    raw_type = event_match.group(1).strip()
    if raw_type.casefold().startswith("raw"):
        return None
    details: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.strip().split(":", 1)
        details[key.strip().casefold().replace(" ", "_")] = value.strip()
    detail = _integer(details.get("detail")) or 0
    x11_time = _integer(details.get("time"))
    event_window = details.get("event") or details.get("window")
    payload: dict[str, Any] = {
        "raw_event_type": raw_type,
        "pointer_x": pointer.get("x"),
        "pointer_y": pointer.get("y"),
        "window_under_pointer": pointer.get("window"),
        "event_window_id": normalize_window_id(event_window),
        "x11_time": x11_time,
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
    if "button" not in folded:
        return None
    if detail in (4, 5, 6, 7) and "release" not in folded:
        # One physical wheel gesture must generate one auditable record.
        return None
    payload.update(
        input_category="mouse_button",
        button=detail,
        pressed="press" in folded,
    )
    if detail in (4, 5, 6, 7):
        payload["input_category"] = "mouse_wheel"
        payload["scroll_direction"] = {
            4: "up",
            5: "down",
            6: "left",
            7: "right",
        }.get(detail)
        payload["input_correlation_id"] = (
            f"wheel:{x11_time}:{detail}" if x11_time is not None else None
        )
    return payload


class ShareableBlackboxCollector(FinalBlackboxCollector):
    """Sanitize every exported file and require one-to-one evidence."""

    def _copy_initial_provenance(self) -> None:
        source = state_root() / "runtime-provenance.json"
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = runtime_identity()
        sanitized = strict_sanitize_runtime_value(payload, self.state.redactions)
        self.paths.runtime_provenance.write_text(
            json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _emit_xinput_block(self, block: list[str]) -> None:
        parsed = parse_shareable_xinput_event(
            block,
            safe_keymap=self.safe_keymap,
            pointer=pointer_snapshot(),
        )
        if parsed is None:
            return
        if parsed.get("input_category") == "text_key":
            self.state.redactions["literal_keyboard_key"] += 1
        self.emit(
            "user",
            {
                **event_base(
                    self.state.session_id,
                    "user_input",
                    "user_input_observed",
                ),
                **parsed,
            },
        )

    def _sanitized_errors(self) -> list[str]:
        return [
            sanitize_generic_string(str(error), self.state.redactions)
            for error in self.state.errors
        ]

    def _write_errors(self) -> None:
        errors = self._sanitized_errors()
        self.paths.errors.write_text(
            "\n".join(errors).rstrip() + ("\n" if errors else ""),
            encoding="utf-8",
        )

    def _write_summary(self, stopped_wall: str, stopped_monotonic_ns: int) -> None:
        original_errors = self.state.errors
        self.state.errors = self._sanitized_errors()
        try:
            super()._write_summary(stopped_wall, stopped_monotonic_ns)
        finally:
            self.state.errors = original_errors

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
        return {
            "scroll": self._correlated_scroll_finding(runtime_records, input_events),
            "workspace_continuity": self._strict_workspace_continuity_finding(
                runtime_records
            ),
            "external_exposure": self._external_exposure_finding(
                runtime_records,
                x11_events,
            ),
        }

    @staticmethod
    def _correlated_scroll_finding(
        runtime_records: list[tuple[dict[str, Any], dict[str, Any]]],
        input_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        wheel_inputs = [
            event
            for event in input_events
            if event.get("input_category") == "mouse_wheel"
        ]
        deliveries = [
            original
            for _wrapped, original in runtime_records
            if original.get("event") == "wheel_event_forwarded"
        ]
        input_by_id: dict[str, list[dict[str, Any]]] = {}
        delivery_by_id: dict[str, list[dict[str, Any]]] = {}
        missing_input_ids = 0
        missing_delivery_ids = 0
        for event in wheel_inputs:
            correlation_id = event.get("input_correlation_id")
            if not correlation_id:
                missing_input_ids += 1
                continue
            input_by_id.setdefault(str(correlation_id), []).append(event)
        for event in deliveries:
            correlation_id = event.get("input_correlation_id")
            if not correlation_id:
                missing_delivery_ids += 1
                continue
            delivery_by_id.setdefault(str(correlation_id), []).append(event)

        all_ids = sorted(set(input_by_id) | set(delivery_by_id))
        failures: list[dict[str, Any]] = []
        matches: list[dict[str, Any]] = []
        for correlation_id in all_ids:
            inputs = input_by_id.get(correlation_id, [])
            outputs = delivery_by_id.get(correlation_id, [])
            delivered = len(outputs) == 1 and bool(outputs[0].get("delivered"))
            route_complete = bool(
                outputs
                and outputs[0].get("runtime_id")
                and outputs[0].get("host_window_id") is not None
                and outputs[0].get("browser_window_id") is not None
            )
            exact = len(inputs) == 1 and len(outputs) == 1 and delivered and route_complete
            record = {
                "input_correlation_id": correlation_id,
                "input_count": len(inputs),
                "delivery_count": len(outputs),
                "delivered": delivered,
                "route_complete": route_complete,
                "runtime_id": outputs[0].get("runtime_id") if outputs else None,
                "host_window_id": outputs[0].get("host_window_id") if outputs else None,
                "browser_window_id": outputs[0].get("browser_window_id") if outputs else None,
            }
            matches.append(record)
            if not exact:
                failures.append(record)

        if failures:
            status = "FAIL_SCROLL_LOSS_DUPLICATION_OR_ROUTE"
        elif missing_input_ids or missing_delivery_ids:
            status = "INDETERMINATE_MISSING_X11_CORRELATION"
        elif wheel_inputs and len(matches) == len(wheel_inputs):
            status = "PASS_ONE_TO_ONE_X11_ROUTE"
        elif wheel_inputs:
            status = "FAIL_SCROLL_UNMATCHED"
        else:
            status = "INDETERMINATE_NO_WHEEL_EVENT"
        return {
            "status": status,
            "system_wheel_events": len(wheel_inputs),
            "delivery_events": len(deliveries),
            "missing_input_correlation_ids": missing_input_ids,
            "missing_delivery_correlation_ids": missing_delivery_ids,
            "matches": matches,
            "failure_count": len(failures),
            "requires_physical_page_confirmation": True,
        }

    @staticmethod
    def _strict_workspace_continuity_finding(
        runtime_records: list[tuple[dict[str, Any], dict[str, Any]]],
    ) -> dict[str, Any]:
        snapshots: list[tuple[int, dict[str, Any]]] = [
            (int(wrapped.get("monotonic_ns", 0) or 0), original)
            for wrapped, original in runtime_records
            if original.get("event") == "workspace_runtime_snapshot"
        ]
        launches: list[tuple[int, str]] = []
        for wrapped, original in runtime_records:
            if original.get("event") == "panel_open_requested":
                runtime_id = str(original.get("runtime_id", ""))
            elif original.get("event") == "browser_launch_requested":
                runtime_id = str(original.get("panel_id", ""))
            else:
                continue
            launches.append((int(wrapped.get("monotonic_ns", 0) or 0), runtime_id))

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
                same_pid = bool(
                    old is not None
                    and new is not None
                    and old.get("pid") is not None
                    and old.get("pid") == new.get("pid")
                )
                same_pgid = bool(
                    old is not None
                    and new is not None
                    and old.get("pgid") is not None
                    and old.get("pgid") == new.get("pgid")
                )
                same_window = bool(
                    old is not None
                    and new is not None
                    and old.get("window_id") is not None
                    and old.get("window_id") == new.get("window_id")
                )
                same_host = bool(
                    old is not None
                    and new is not None
                    and old.get("host_window_id") is not None
                    and old.get("host_window_id") == new.get("host_window_id")
                )
                if (
                    old is None
                    or new is None
                    or not same_pid
                    or not same_pgid
                    or not same_window
                    or not same_host
                    or relaunches
                ):
                    cycle_failures.append(
                        {
                            "runtime_id": runtime_id,
                            "present_before": old is not None,
                            "present_after": new is not None,
                            "same_pid": same_pid,
                            "same_pgid": same_pgid,
                            "same_window_id": same_window,
                            "same_host_window_id": same_host,
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
            status = "PASS_SAME_PID_PGID_WINDOW_AND_HOST"
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
    collector = ShareableBlackboxCollector(
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
        description="Diagnóstico compartilhável com correlação X11 exata"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
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
    "ShareableBlackboxCollector",
    "main",
    "parse_shareable_xinput_event",
    "run_blackbox",
]


if __name__ == "__main__":
    raise SystemExit(main())
