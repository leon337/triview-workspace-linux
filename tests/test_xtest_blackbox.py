from __future__ import annotations

import shutil
import subprocess
from types import SimpleNamespace
from typing import Any

from triview_workspace.diagnostic_blackbox_xtest import (
    XTestAwareXephyrBlackboxCollector,
    annotate_xinput_origin,
    xtest_device_ids,
)


def _runtime_record(monotonic_ns: int, **event: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    wrapped = {"monotonic_ns": monotonic_ns, "runtime_event": event}
    return wrapped, event


def _wheel_event(
    correlation_id: str,
    *,
    synthetic: bool,
) -> dict[str, Any]:
    return {
        "input_category": "mouse_wheel",
        "input_correlation_id": correlation_id,
        "event_window_id": 100,
        "window_under_pointer": 100,
        "pointer_x": 120,
        "pointer_y": 130,
        "synthetic": synthetic,
        "synthetic_classifier_available": True,
    }


def _delivery(correlation_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return _runtime_record(
        200,
        event="wheel_event_forwarded",
        input_correlation_id=correlation_id,
        runtime_id="agents::architect",
        host_window_id=900,
        browser_window_id="77",
        host_ancestry=[900, 500, 100],
        browser_ancestry=[77, 900, 500, 100],
        host_x=10,
        host_y=20,
        host_width=300,
        host_height=250,
        pointer_x=120,
        pointer_y=130,
        delivered=True,
    )


def test_xtest_device_discovery_keeps_only_virtual_device_ids(monkeypatch: Any) -> None:
    monkeypatch.setattr(shutil, "which", lambda command: "/usr/bin/xinput")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=(
                "Virtual core pointer id=2 [master pointer]\n"
                "  Virtual core XTEST pointer id=4 [slave pointer]\n"
                "Virtual core keyboard id=3 [master keyboard]\n"
                "  Virtual core XTEST keyboard id=5 [slave keyboard]\n"
            ),
        ),
    )

    assert xtest_device_ids() == frozenset({4, 5})


def test_xi2_xtest_release_is_retained_but_marked_synthetic() -> None:
    payload = annotate_xinput_origin(
        {
            "input_category": "mouse_wheel",
            "input_correlation_id": "wheel:101:5",
        },
        [
            "EVENT type 16 (ButtonRelease)\n",
            "    device: 2 (4)\n",
            "    detail: 5\n",
            "    time: 101\n",
        ],
        synthetic_device_ids=frozenset({4, 5}),
    )

    assert payload["device_id"] == 2
    assert payload["source_device_id"] == 4
    assert payload["synthetic"] is True
    assert payload["synthetic_origin"] == "x11_xtest"
    assert payload["synthetic_classifier_available"] is True


def test_direct_xtest_device_without_source_is_still_synthetic() -> None:
    payload = annotate_xinput_origin(
        {"input_category": "mouse_wheel"},
        [
            "EVENT type 16 (ButtonRelease)\n",
            "    device: 4\n",
            "    detail: 5\n",
        ],
        synthetic_device_ids=frozenset({4, 5}),
    )

    assert payload["device_id"] == 4
    assert payload["source_device_id"] is None
    assert payload["synthetic"] is True
    assert payload["synthetic_classifier_available"] is True


def test_master_device_without_source_disables_classifier() -> None:
    payload = annotate_xinput_origin(
        {"input_category": "mouse_wheel"},
        [
            "EVENT type 16 (ButtonRelease)\n",
            "    device: 2\n",
            "    detail: 5\n",
        ],
        synthetic_device_ids=frozenset({4, 5}),
    )

    assert payload["device_id"] == 2
    assert payload["source_device_id"] is None
    assert payload["synthetic"] is False
    assert payload["synthetic_classifier_available"] is False


def test_missing_xi2_device_pair_disables_classifier() -> None:
    payload = annotate_xinput_origin(
        {"input_category": "mouse_wheel"},
        [
            "EVENT type 16 (ButtonRelease)\n",
            "    detail: 5\n",
            "    time: 101\n",
        ],
        synthetic_device_ids=frozenset({4, 5}),
    )

    assert payload["device_id"] is None
    assert payload["source_device_id"] is None
    assert payload["synthetic"] is False
    assert payload["synthetic_classifier_available"] is False


def test_scroll_verdict_ignores_forwarded_xtest_copy() -> None:
    inputs = [
        _wheel_event("wheel:100:5", synthetic=False),
        _wheel_event("wheel:101:5", synthetic=True),
    ]
    finding = XTestAwareXephyrBlackboxCollector._correlated_scroll_finding(
        [_delivery("wheel:100:5")],
        inputs,
    )

    assert finding["status"] == "PASS_ONE_TO_ONE_MATCHED_X11_PANEL_FILTERED_XTEST"
    assert finding["observed_wheel_events"] == 2
    assert finding["physical_wheel_events"] == 1
    assert finding["synthetic_wheel_events"] == 1
    assert finding["failure_count"] == 0


def test_scroll_verdict_still_fails_real_physical_loss() -> None:
    inputs = [
        _wheel_event("wheel:100:5", synthetic=False),
        _wheel_event("wheel:102:5", synthetic=False),
        _wheel_event("wheel:101:5", synthetic=True),
    ]
    finding = XTestAwareXephyrBlackboxCollector._correlated_scroll_finding(
        [_delivery("wheel:100:5")],
        inputs,
    )

    assert finding["status"] == "FAIL_SCROLL_LOSS_DUPLICATION_OR_WRONG_PANEL"
    assert finding["failure_count"] == 1
    assert finding["physical_wheel_events"] == 2
    assert finding["synthetic_wheel_events"] == 1


def test_missing_xtest_classifier_is_indeterminate() -> None:
    event = _wheel_event("wheel:100:5", synthetic=False)
    event["synthetic_classifier_available"] = False
    finding = XTestAwareXephyrBlackboxCollector._correlated_scroll_finding(
        [_delivery("wheel:100:5")],
        [event],
    )

    assert finding["status"] == "INDETERMINATE_XTEST_CLASSIFIER_UNAVAILABLE"
