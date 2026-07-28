"""Final shareable diagnostics for the Xephyr-contained TriView candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from triview_workspace.diagnostic_blackbox import (
    DEFAULT_TIMEOUT_SECONDS,
    DiagnosticWindow,
    runtime_identity,
    state_root,
)
from triview_workspace.diagnostic_blackbox_final import (
    normalize_window_id,
    strict_sanitize_runtime_value,
)
from triview_workspace.diagnostic_blackbox_verified import (
    VerifiedBlackboxCollector,
    input_route_windows,
)


def delivery_route_windows_with_ancestry(event: dict[str, Any]) -> set[int]:
    """Return host/browser windows and every ancestry item captured live."""

    windows: set[int] = set()
    for key in ("host_window_id", "browser_window_id"):
        window_id = normalize_window_id(event.get(key))
        if window_id is not None:
            windows.add(window_id)
    for key in ("host_ancestry", "browser_ancestry"):
        values = event.get(key, [])
        if not isinstance(values, list):
            continue
        for value in values:
            window_id = normalize_window_id(value)
            if window_id is not None:
                windows.add(window_id)
    return windows


class XephyrVerifiedBlackboxCollector(VerifiedBlackboxCollector):
    """Verify nested containment, live ancestry and final runtime provenance."""

    def _refresh_runtime_provenance(self) -> None:
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

    def finalize(self) -> Path:
        self._refresh_runtime_provenance()
        return super().finalize()

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
        indeterminate: list[dict[str, Any]] = []
        matches: list[dict[str, Any]] = []
        for correlation_id in all_ids:
            inputs = input_by_id.get(correlation_id, [])
            outputs = delivery_by_id.get(correlation_id, [])
            one_to_one = len(inputs) == 1 and len(outputs) == 1
            delivered = bool(one_to_one and outputs[0].get("delivered"))
            input_windows = input_route_windows(inputs[0]) if len(inputs) == 1 else set()
            output_windows = (
                delivery_route_windows_with_ancestry(outputs[0])
                if len(outputs) == 1
                else set()
            )
            route_complete = bool(
                outputs
                and outputs[0].get("runtime_id")
                and outputs[0].get("host_window_id") is not None
                and outputs[0].get("browser_window_id") is not None
                and outputs[0].get("host_ancestry")
                and outputs[0].get("browser_ancestry")
            )
            window_evidence_available = bool(input_windows and output_windows)
            route_matches = bool(input_windows & output_windows)
            exact = bool(
                one_to_one
                and delivered
                and route_complete
                and window_evidence_available
                and route_matches
            )
            record = {
                "input_correlation_id": correlation_id,
                "input_count": len(inputs),
                "delivery_count": len(outputs),
                "delivered": delivered,
                "route_complete": route_complete,
                "window_evidence_available": window_evidence_available,
                "input_window_ids": sorted(input_windows),
                "delivery_window_ids": sorted(output_windows),
                "route_matches_physical_window": route_matches,
                "runtime_id": outputs[0].get("runtime_id") if outputs else None,
                "host_window_id": outputs[0].get("host_window_id") if outputs else None,
                "browser_window_id": outputs[0].get("browser_window_id") if outputs else None,
            }
            matches.append(record)
            if exact:
                continue
            if one_to_one and delivered and route_complete and not window_evidence_available:
                indeterminate.append(record)
            else:
                failures.append(record)

        if failures:
            status = "FAIL_SCROLL_LOSS_DUPLICATION_OR_WRONG_PANEL"
        elif indeterminate or missing_input_ids or missing_delivery_ids:
            status = "INDETERMINATE_MISSING_X11_ROUTE_EVIDENCE"
        elif wheel_inputs and len(matches) == len(wheel_inputs) and all(
            record["route_matches_physical_window"] for record in matches
        ):
            status = "PASS_ONE_TO_ONE_MATCHED_X11_ANCESTRY"
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
            "indeterminate_count": len(indeterminate),
            "requires_physical_page_confirmation": True,
        }

    @staticmethod
    def _external_exposure_finding(
        runtime_records: list[tuple[dict[str, Any], dict[str, Any]]],
        x11_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        nested_ready = [
            original
            for _wrapped, original in runtime_records
            if original.get("event") == "browser_nested_window_ready"
        ]
        nested_embedded = [
            original
            for _wrapped, original in runtime_records
            if original.get("event") == "browser_launch_embedded"
            and original.get("containment") == "nested_xephyr"
        ]
        unsafe_runtime_events = [
            event
            for event in [*nested_ready, *nested_embedded]
            if event.get("external_root_mapping_possible") is not False
        ]
        host_visible_brave = [
            event
            for event in x11_events
            if event.get("event_type") == "window_created_observed"
            and bool(event.get("externally_visible_candidate"))
            and str(event.get("window_class", "")).casefold().startswith("triview-")
        ]
        if unsafe_runtime_events or host_visible_brave:
            status = "FAIL_EXTERNAL_VISIBILITY_BEFORE_EMBED"
        elif nested_ready and len(nested_ready) == len(nested_embedded):
            status = "PASS_NESTED_X11_CONTAINMENT"
        else:
            status = "INDETERMINATE_INSUFFICIENT_NESTED_EVENTS"
        return {
            "status": status,
            "nested_ready_events": len(nested_ready),
            "nested_embedded_events": len(nested_embedded),
            "unsafe_runtime_events": len(unsafe_runtime_events),
            "host_visible_brave_window_ids": sorted(
                {
                    normalize_window_id(event.get("window_id"))
                    for event in host_visible_brave
                    if normalize_window_id(event.get("window_id")) is not None
                }
            ),
            "containment": "nested_xephyr",
        }


def run_blackbox(
    output_dir: Path,
    timeout_seconds: int,
    *,
    auto_launch: bool = False,
    auto_stop_on_application_exit: bool = False,
) -> Path:
    collector = XephyrVerifiedBlackboxCollector(
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
        description="Diagnóstico final do TriView com contenção Xephyr"
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
    "XephyrVerifiedBlackboxCollector",
    "delivery_route_windows_with_ancestry",
    "main",
    "run_blackbox",
]


if __name__ == "__main__":
    raise SystemExit(main())
