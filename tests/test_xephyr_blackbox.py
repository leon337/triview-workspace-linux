from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from triview_workspace.diagnostic_blackbox_xephyr import (
    XephyrVerifiedBlackboxCollector,
    delivery_route_windows_with_ancestry,
)


def _runtime_record(monotonic_ns: int, **event: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    wrapped = {"monotonic_ns": monotonic_ns, "runtime_event": event}
    return wrapped, event


def _input(
    correlation_id: str,
    window_id: int,
    *,
    pointer_x: int,
    pointer_y: int,
) -> dict[str, Any]:
    return {
        "input_category": "mouse_wheel",
        "input_correlation_id": correlation_id,
        "event_window_id": window_id,
        "window_under_pointer": window_id,
        "pointer_x": pointer_x,
        "pointer_y": pointer_y,
    }


def _delivery(
    correlation_id: str,
    *,
    runtime_id: str,
    host_window_id: int,
    browser_window_id: str,
    host_ancestry: list[int],
    browser_ancestry: list[int],
    host_geometry: tuple[int, int, int, int] | None,
    pointer_x: int,
    pointer_y: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    geometry = host_geometry or (None, None, None, None)
    return _runtime_record(
        200,
        event="wheel_event_forwarded",
        input_correlation_id=correlation_id,
        runtime_id=runtime_id,
        host_window_id=host_window_id,
        browser_window_id=browser_window_id,
        host_ancestry=host_ancestry,
        browser_ancestry=browser_ancestry,
        host_x=geometry[0],
        host_y=geometry[1],
        host_width=geometry[2],
        host_height=geometry[3],
        pointer_x=pointer_x,
        pointer_y=pointer_y,
        delivered=True,
    )


def test_delivery_route_includes_live_ancestry() -> None:
    assert delivery_route_windows_with_ancestry(
        {
            "host_window_id": 900,
            "browser_window_id": "77",
            "host_ancestry": [900, 500, 100],
            "browser_ancestry": [77, 900, 500, 100],
        }
    ) == {77, 100, 500, 900}


def test_scroll_passes_with_shared_top_level_and_pointer_inside_target_panel() -> None:
    correlation_id = "wheel:100:5"
    finding = XephyrVerifiedBlackboxCollector._correlated_scroll_finding(
        [
            _delivery(
                correlation_id,
                runtime_id="agents::architect",
                host_window_id=900,
                browser_window_id="77",
                host_ancestry=[900, 500, 100],
                browser_ancestry=[77, 900, 500, 100],
                host_geometry=(0, 0, 400, 700),
                pointer_x=120,
                pointer_y=300,
            )
        ],
        [
            _input(
                correlation_id,
                100,
                pointer_x=120,
                pointer_y=300,
            )
        ],
    )

    assert finding["status"] == "PASS_ONE_TO_ONE_MATCHED_X11_PANEL_GEOMETRY"
    assert finding["failure_count"] == 0
    match = finding["matches"][0]
    assert match["shared_ancestor_observed"] is True
    assert match["route_matches_physical_panel"] is True
    assert match["input_pointer_inside_host"] is True


def test_scroll_blocks_wrong_sibling_panel_under_same_top_level() -> None:
    correlation_id = "wheel:100:5"
    finding = XephyrVerifiedBlackboxCollector._correlated_scroll_finding(
        [
            _delivery(
                correlation_id,
                runtime_id="agents::implementer",
                host_window_id=901,
                browser_window_id="88",
                host_ancestry=[901, 501, 100],
                browser_ancestry=[88, 901, 501, 100],
                host_geometry=(450, 0, 400, 700),
                pointer_x=120,
                pointer_y=300,
            )
        ],
        [
            _input(
                correlation_id,
                100,
                pointer_x=120,
                pointer_y=300,
            )
        ],
    )

    assert finding["status"] == "FAIL_SCROLL_LOSS_DUPLICATION_OR_WRONG_PANEL"
    assert finding["failure_count"] == 1
    match = finding["matches"][0]
    assert match["shared_ancestor_observed"] is True
    assert match["delivery_pointer_inside_host"] is False
    assert match["route_matches_physical_panel"] is False


def test_scroll_without_geometry_is_indeterminate_and_never_passes() -> None:
    correlation_id = "wheel:100:5"
    finding = XephyrVerifiedBlackboxCollector._correlated_scroll_finding(
        [
            _delivery(
                correlation_id,
                runtime_id="agents::architect",
                host_window_id=900,
                browser_window_id="77",
                host_ancestry=[900, 500, 100],
                browser_ancestry=[77, 900, 500, 100],
                host_geometry=None,
                pointer_x=120,
                pointer_y=300,
            )
        ],
        [
            _input(
                correlation_id,
                100,
                pointer_x=120,
                pointer_y=300,
            )
        ],
    )

    assert finding["status"] == "INDETERMINATE_MISSING_X11_ROUTE_EVIDENCE"
    assert finding["failure_count"] == 0
    assert finding["indeterminate_count"] == 1


def test_nested_containment_pass_requires_authenticated_safe_events() -> None:
    records = [
        _runtime_record(
            10,
            event="browser_nested_window_ready",
            browser_window_id="77",
            host_window_id=900,
            containment="nested_xephyr",
            nested_display_authenticated=True,
            external_root_mapping_possible=False,
        ),
        _runtime_record(
            20,
            event="browser_launch_embedded",
            browser_window_id="77",
            host_window_id=900,
            containment="nested_xephyr",
            nested_display_authenticated=True,
            external_root_mapping_possible=False,
        ),
    ]

    finding = XephyrVerifiedBlackboxCollector._external_exposure_finding(records, [])

    assert finding["status"] == "PASS_AUTHENTICATED_NESTED_X11_CONTAINMENT"
    assert finding["nested_ready_events"] == 1
    assert finding["nested_embedded_events"] == 1


def test_nested_containment_fails_on_unauthenticated_or_unsafe_event() -> None:
    records = [
        _runtime_record(
            10,
            event="browser_nested_window_ready",
            browser_window_id="77",
            host_window_id=900,
            containment="nested_xephyr",
            nested_display_authenticated=False,
            external_root_mapping_possible=False,
        ),
        _runtime_record(
            20,
            event="browser_launch_embedded",
            browser_window_id="77",
            host_window_id=900,
            containment="nested_xephyr",
            nested_display_authenticated=True,
            external_root_mapping_possible=False,
        ),
    ]

    finding = XephyrVerifiedBlackboxCollector._external_exposure_finding(records, [])

    assert finding["status"] == "FAIL_EXTERNAL_VISIBILITY_BEFORE_EMBED"


def test_provenance_is_refreshed_after_the_runtime_launch(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    state_home = tmp_path / "state"
    state_root = state_home / "triview-workspace"
    state_root.mkdir(parents=True)
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))
    (state_root / "runtime-provenance.json").write_text(
        json.dumps({"runtime_sha": "old", "backend": "old"}),
        encoding="utf-8",
    )
    collector = XephyrVerifiedBlackboxCollector(
        tmp_path / "output",
        30,
        auto_launch=False,
    )
    try:
        (state_root / "runtime-provenance.json").write_text(
            json.dumps(
                {
                    "runtime_sha": "new",
                    "backend": "XephyrEmbeddedBraveBrowserBackend",
                }
            ),
            encoding="utf-8",
        )
        collector._refresh_runtime_provenance()
        exported = json.loads(collector.paths.runtime_provenance.read_text(encoding="utf-8"))
        assert exported["runtime_sha"] == "new"
        assert exported["backend"] == "XephyrEmbeddedBraveBrowserBackend"
    finally:
        collector.request_stop("test_cleanup")
        for writer in collector.writers.values():
            writer.close()
