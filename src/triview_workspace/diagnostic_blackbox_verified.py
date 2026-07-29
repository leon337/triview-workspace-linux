"""Verified shareable diagnostics with panel-aware wheel correlation."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from triview_workspace.diagnostic_blackbox import (
    DEFAULT_TIMEOUT_SECONDS,
    DiagnosticWindow,
)
from triview_workspace.diagnostic_blackbox_final import normalize_window_id
from triview_workspace.diagnostic_blackbox_shareable import (
    ShareableBlackboxCollector,
)


def input_route_windows(event: dict[str, Any]) -> set[int]:
    """Return every concrete X11 window associated with one physical input."""

    windows: set[int] = set()
    for key in ("event_window_id", "window_under_pointer"):
        window_id = normalize_window_id(event.get(key))
        if window_id is not None:
            windows.add(window_id)
    return windows


def delivery_route_windows(event: dict[str, Any]) -> set[int]:
    """Return the registered host and embedded Browser window for one delivery."""

    windows: set[int] = set()
    for key in ("host_window_id", "browser_window_id"):
        window_id = normalize_window_id(event.get(key))
        if window_id is not None:
            windows.add(window_id)
    return windows


class VerifiedBlackboxCollector(ShareableBlackboxCollector):
    """Require input and delivery to name the same Browser route before PASS."""

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
                delivery_route_windows(outputs[0]) if len(outputs) == 1 else set()
            )
            route_complete = len(output_windows) == 2 and bool(
                outputs
                and outputs[0].get("runtime_id")
                and outputs[0].get("host_window_id") is not None
                and outputs[0].get("browser_window_id") is not None
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
            status = "PASS_ONE_TO_ONE_MATCHED_X11_PANEL"
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


def run_blackbox(
    output_dir: Path,
    timeout_seconds: int,
    *,
    auto_launch: bool = False,
    auto_stop_on_application_exit: bool = False,
) -> Path:
    collector = VerifiedBlackboxCollector(
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
        description="Diagnóstico compartilhável com painel X11 verificado"
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
    "VerifiedBlackboxCollector",
    "delivery_route_windows",
    "input_route_windows",
    "main",
    "run_blackbox",
]


if __name__ == "__main__":
    raise SystemExit(main())
