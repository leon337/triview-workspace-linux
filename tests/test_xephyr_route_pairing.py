from __future__ import annotations

from typing import Any

from triview_workspace.diagnostic_blackbox_xephyr import (
    XephyrVerifiedBlackboxCollector,
)


def _record(**event: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    wrapped = {"monotonic_ns": 200, "runtime_event": event}
    return wrapped, event


def test_scroll_blocks_browser_window_from_a_different_host() -> None:
    correlation_id = "wheel:100:5"
    records = [
        _record(
            event="wheel_event_forwarded",
            input_correlation_id=correlation_id,
            runtime_id="agents::architect",
            host_window_id=900,
            browser_window_id="88",
            host_ancestry=[900, 500, 100],
            browser_ancestry=[88, 901, 500, 100],
            host_x=0,
            host_y=0,
            host_width=400,
            host_height=700,
            pointer_x=120,
            pointer_y=300,
            delivered=True,
        )
    ]
    inputs = [
        {
            "input_category": "mouse_wheel",
            "input_correlation_id": correlation_id,
            "event_window_id": 100,
            "window_under_pointer": 100,
            "pointer_x": 120,
            "pointer_y": 300,
        }
    ]

    finding = XephyrVerifiedBlackboxCollector._correlated_scroll_finding(
        records,
        inputs,
    )

    assert finding["status"] == "FAIL_SCROLL_LOSS_DUPLICATION_OR_WRONG_PANEL"
    assert finding["failure_count"] == 1
    match = finding["matches"][0]
    assert match["host_contains_browser"] is False
    assert match["route_matches_physical_panel"] is True
    assert match["route_complete"] is False
