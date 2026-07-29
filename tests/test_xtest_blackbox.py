from __future__ import annotations

import os
import select
import shutil
import subprocess
import time
from types import SimpleNamespace
from typing import Any

import pytest

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


def _read_button_release_block(
    process: subprocess.Popen[str],
    *,
    timeout: float = 6.0,
) -> list[str]:
    assert process.stdout is not None
    deadline = time.monotonic() + timeout
    block: list[str] = []
    while time.monotonic() < deadline:
        readable, _writable, _errors = select.select(
            [process.stdout], [], [], min(0.25, deadline - time.monotonic())
        )
        if not readable:
            continue
        line = process.stdout.readline()
        if not line:
            break
        if line.lstrip().startswith("EVENT type"):
            if block and "(ButtonRelease)" in block[0]:
                return block
            block = [line]
        elif block:
            block.append(line)
    if block and "(ButtonRelease)" in block[0]:
        return block
    raise AssertionError("ButtonRelease XI2 não observado")


@pytest.mark.skipif(
    os.environ.get("TRIVIEW_RUN_X11_INTEGRATION") != "1",
    reason="executado somente na etapa X11 dedicada da CI",
)
def test_real_xdotool_wheel_is_identified_as_xtest() -> None:
    xinput = shutil.which("xinput")
    xdotool = shutil.which("xdotool")
    stdbuf = shutil.which("stdbuf")
    if not xinput or not xdotool or not stdbuf or not os.environ.get("DISPLAY"):
        pytest.skip("xinput/xdotool/X11 indisponível")

    synthetic_ids = xtest_device_ids()
    assert synthetic_ids
    process = subprocess.Popen(
        [stdbuf, "-oL", xinput, "test-xi2", "--root"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    try:
        time.sleep(0.25)
        subprocess.run([xdotool, "click", "5"], check=True, timeout=3)
        block = _read_button_release_block(process)
        payload = annotate_xinput_origin(
            {"input_category": "mouse_wheel"},
            block,
            synthetic_device_ids=synthetic_ids,
        )
        assert payload["synthetic"] is True
        assert payload["source_device_id"] in synthetic_ids
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
