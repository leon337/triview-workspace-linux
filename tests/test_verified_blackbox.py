from __future__ import annotations

from typing import Any

from triview_workspace.diagnostic_blackbox_verified import (
    VerifiedBlackboxCollector,
    delivery_route_windows,
    input_route_windows,
)


def _runtime_record(monotonic_ns: int, **event: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    wrapped = {"monotonic_ns": monotonic_ns, "runtime_event": event}
    return wrapped, event


def _input(
    correlation_id: str,
    *,
    event_window_id: int | None,
    window_under_pointer: int | None,
) -> dict[str, Any]:
    return {
        "input_category": "mouse_wheel",
        "input_correlation_id": correlation_id,
        "event_window_id": event_window_id,
        "window_under_pointer": window_under_pointer,
    }


def _delivery(
    correlation_id: str,
    *,
    runtime_id: str,
    host_window_id: int,
    browser_window_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return _runtime_record(
        200,
        event="wheel_event_forwarded",
        input_correlation_id=correlation_id,
        runtime_id=runtime_id,
        host_window_id=host_window_id,
        browser_window_id=browser_window_id,
        delivered=True,
    )


def test_window_helpers_normalize_host_browser_and_input_windows() -> None:
    assert input_route_windows(
        _input(
            "wheel:100:5",
            event_window_id=900,
            window_under_pointer=77,
        )
    ) == {77, 900}
    assert delivery_route_windows(
        {
            "host_window_id": 900,
            "browser_window_id": "0x4d",
        }
    ) == {77, 900}


def test_verified_scroll_passes_when_input_matches_host_or_browser() -> None:
    correlation_id = "wheel:100:5"
    inputs = [
        _input(
            correlation_id,
            event_window_id=900,
            window_under_pointer=77,
        )
    ]
    records = [
        _delivery(
            correlation_id,
            runtime_id="agents::architect",
            host_window_id=900,
            browser_window_id="77",
        )
    ]

    finding = VerifiedBlackboxCollector._correlated_scroll_finding(records, inputs)

    assert finding["status"] == "PASS_ONE_TO_ONE_MATCHED_X11_PANEL"
    assert finding["failure_count"] == 0
    match = finding["matches"][0]
    assert match["route_matches_physical_window"] is True
    assert match["input_window_ids"] == [77, 900]
    assert match["delivery_window_ids"] == [77, 900]


def test_verified_scroll_blocks_single_delivery_to_wrong_panel() -> None:
    correlation_id = "wheel:100:5"
    inputs = [
        _input(
            correlation_id,
            event_window_id=900,
            window_under_pointer=77,
        )
    ]
    records = [
        _delivery(
            correlation_id,
            runtime_id="social::youtube",
            host_window_id=901,
            browser_window_id="88",
        )
    ]

    finding = VerifiedBlackboxCollector._correlated_scroll_finding(records, inputs)

    assert finding["status"] == "FAIL_SCROLL_LOSS_DUPLICATION_OR_WRONG_PANEL"
    assert finding["failure_count"] == 1
    match = finding["matches"][0]
    assert match["input_count"] == 1
    assert match["delivery_count"] == 1
    assert match["delivered"] is True
    assert match["route_complete"] is True
    assert match["route_matches_physical_window"] is False
    assert match["input_window_ids"] == [77, 900]
    assert match["delivery_window_ids"] == [88, 901]


def test_verified_scroll_is_indeterminate_without_input_window_evidence() -> None:
    correlation_id = "wheel:100:5"
    inputs = [
        _input(
            correlation_id,
            event_window_id=None,
            window_under_pointer=None,
        )
    ]
    records = [
        _delivery(
            correlation_id,
            runtime_id="agents::architect",
            host_window_id=900,
            browser_window_id="77",
        )
    ]

    finding = VerifiedBlackboxCollector._correlated_scroll_finding(records, inputs)

    assert finding["status"] == "INDETERMINATE_MISSING_X11_ROUTE_EVIDENCE"
    assert finding["failure_count"] == 0
    assert finding["indeterminate_count"] == 1


def test_verified_scroll_still_rejects_loss_and_duplication() -> None:
    first = "wheel:100:5"
    second = "wheel:101:5"
    inputs = [
        _input(first, event_window_id=900, window_under_pointer=77),
        _input(second, event_window_id=900, window_under_pointer=77),
    ]
    records = [
        _delivery(
            first,
            runtime_id="agents::architect",
            host_window_id=900,
            browser_window_id="77",
        ),
        _delivery(
            first,
            runtime_id="agents::architect",
            host_window_id=900,
            browser_window_id="77",
        ),
    ]

    finding = VerifiedBlackboxCollector._correlated_scroll_finding(records, inputs)

    assert finding["status"] == "FAIL_SCROLL_LOSS_DUPLICATION_OR_WRONG_PANEL"
    assert finding["failure_count"] == 2


def test_candidate_diagnostic_uses_verified_collector() -> None:
    script = open("scripts/candidate-diagnose.sh", encoding="utf-8").read()

    assert "triview_workspace.diagnostic_blackbox_verified" in script
    assert "diagnostic_blackbox_shareable" in script
    assert "diagnostic_blackbox_final" in script
