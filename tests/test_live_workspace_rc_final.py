from __future__ import annotations

import inspect
import json
from collections import Counter
from pathlib import Path
from typing import Any

import triview_workspace.gui_rc4_atomic as atomic_gui
from triview_workspace.diagnostic_blackbox_final import (
    FinalBlackboxCollector,
    sanitize_url_origin,
    strict_sanitize_runtime_value,
    strict_sanitized_arguments,
)
from triview_workspace.diagnostic_blackbox_verified import VerifiedBlackboxCollector
from triview_workspace.engines.browser_wheel_bridge import BrowserWheelRoute
from triview_workspace.engines.browser_wheel_worker import WHEEL_BUTTONS


def _wrapped(monotonic_ns: int, **runtime_event: Any) -> dict[str, Any]:
    return {
        "monotonic_ns": monotonic_ns,
        "runtime_event": runtime_event,
    }


def test_url_sanitization_removes_private_paths_queries_and_fragments() -> None:
    assert sanitize_url_origin(
        "https://chatgpt.com/c/secret-conversation?token=abc#message"
    ) == "https://chatgpt.com/"
    assert sanitize_url_origin(
        "https://github.com/private-owner/private-repo/issues/12"
    ) == "https://github.com/"
    assert sanitize_url_origin("file:///home/leo/private.txt") == "[REDACTED_URL]"


def test_process_argument_allowlist_drops_private_values() -> None:
    redactions: Counter[str] = Counter()
    sanitized = strict_sanitized_arguments(
        "/opt/brave/brave "
        "--app=https://chatgpt.com/c/private-id?token=abc "
        "--user-data-dir=/home/leo/.private-profile "
        "--token=secret "
        "--class=TriView-agent "
        "typed-private-value",
        redactions,
    )

    assert "private-id" not in sanitized
    assert "abc" not in sanitized
    assert "/home/leo" not in sanitized
    assert "secret" not in sanitized
    assert "typed-private-value" not in sanitized
    assert "--app=https://chatgpt.com/" in sanitized
    assert "--user-data-dir=[PROFILE_DIR]" in sanitized
    assert "--class=TriView-agent" in sanitized


def test_runtime_sanitization_is_origin_only_and_redacts_local_resources() -> None:
    redactions: Counter[str] = Counter()
    sanitized = strict_sanitize_runtime_value(
        {
            "url": "https://chatgpt.com/c/private-id?x=1",
            "target": "file:///home/leo/private.pdf",
            "message_text": "private message",
            "command": [
                "/opt/brave/brave",
                "--app=https://github.com/private/repo",
            ],
            "profile_dir": "/home/leo/.local/private-profile",
        },
        redactions,
    )

    assert sanitized["url"] == "https://chatgpt.com/"
    assert sanitized["target"] == "[LOCAL_RESOURCE]"
    assert sanitized["message_text"] == "[REDACTED]"
    assert "private/repo" not in " ".join(sanitized["command"])
    assert sanitized["profile_dir"].startswith("[LOCAL_PATH]")


def test_external_exposure_fails_on_first_visible_candidate() -> None:
    records = [
        _wrapped(
            10,
            event="browser_candidate_forced_hidden",
            browser_window_id="77",
            visible_before_hide=True,
        ),
        _wrapped(
            20,
            event="browser_window_hidden_staging",
            browser_window_id="77",
            visible_before=False,
        ),
        _wrapped(
            30,
            event="browser_launch_embedded",
            browser_window_id="77",
        ),
    ]

    finding = FinalBlackboxCollector._external_exposure_finding(
        [(item, item["runtime_event"]) for item in records],
        [],
    )

    assert finding["status"] == "FAIL_EXTERNAL_VISIBILITY_BEFORE_EMBED"
    assert finding["visible_before_hide"] == 1


def test_external_exposure_never_passes_without_complete_evidence() -> None:
    finding = FinalBlackboxCollector._external_exposure_finding([], [])

    assert finding["status"] == "INDETERMINATE_INSUFFICIENT_EVENTS"


def test_external_exposure_passes_only_with_forced_hide_staging_and_embed() -> None:
    records = [
        _wrapped(
            10,
            event="browser_candidate_forced_hidden",
            browser_window_id="77",
            visible_before_hide=False,
        ),
        _wrapped(
            20,
            event="browser_window_hidden_staging",
            browser_window_id="77",
            visible_before=False,
        ),
        _wrapped(
            30,
            event="browser_launch_embedded",
            browser_window_id="77",
        ),
    ]

    finding = FinalBlackboxCollector._external_exposure_finding(
        [(item, item["runtime_event"]) for item in records],
        [],
    )

    assert finding["status"] == "PASS_TECHNICAL_NO_EXTERNAL_VISIBILITY"


def test_continuity_pass_requires_same_pid_and_window_without_relaunch() -> None:
    runtime = {
        "workspace_id": "agents",
        "panel_id": "architect",
        "runtime_id": "agents::architect",
        "active": True,
        "pid": 101,
        "pgid": 101,
        "window_id": "77",
        "host_window_id": 900,
    }
    records = [
        _wrapped(
            10,
            event="workspace_runtime_snapshot",
            phase="parked",
            workspace_id="agents",
            runtimes=[runtime],
        ),
        _wrapped(
            30,
            event="workspace_runtime_snapshot",
            phase="restored",
            workspace_id="agents",
            runtimes=[runtime],
        ),
    ]

    finding = FinalBlackboxCollector._workspace_continuity_finding(
        [(item, item["runtime_event"]) for item in records]
    )

    assert finding["status"] == "PASS_SAME_PID_AND_WINDOW_ID"
    assert finding["failure_count"] == 0


def test_continuity_fails_on_window_change_or_relaunch() -> None:
    before = {
        "runtime_id": "agents::architect",
        "active": True,
        "pid": 101,
        "window_id": "77",
    }
    after = {
        "runtime_id": "agents::architect",
        "active": True,
        "pid": 101,
        "window_id": "88",
    }
    records = [
        _wrapped(
            10,
            event="workspace_runtime_snapshot",
            phase="parked",
            workspace_id="agents",
            runtimes=[before],
        ),
        _wrapped(
            20,
            event="browser_launch_requested",
            panel_id="agents::architect",
        ),
        _wrapped(
            30,
            event="workspace_runtime_snapshot",
            phase="restored",
            workspace_id="agents",
            runtimes=[after],
        ),
    ]

    finding = FinalBlackboxCollector._workspace_continuity_finding(
        [(item, item["runtime_event"]) for item in records]
    )

    assert finding["status"] == "FAIL_RUNTIME_CHANGED_OR_RELAUNCHED"
    failure = finding["cycles"][0]["failures"][0]
    assert failure["same_pid"] is True
    assert failure["same_window_id"] is False
    assert failure["relaunches"] == 1


def test_wheel_route_payload_contains_only_technical_identifiers() -> None:
    route = BrowserWheelRoute(
        runtime_id="agents::architect",
        host_window_id=900,
        browser_window_id="77",
    )

    assert route.as_payload() == {
        "runtime_id": "agents::architect",
        "host_window_id": 900,
        "browser_window_id": "77",
    }
    assert WHEEL_BUTTONS == (4, 5)


def test_wheel_worker_captures_no_keyboard_events() -> None:
    source = Path(
        "src/triview_workspace/engines/browser_wheel_worker.py"
    ).read_text(encoding="utf-8")

    assert "XGrabKey" not in source
    assert "KeyPress" not in source
    assert "BUTTON_PRESS_MASK | BUTTON_RELEASE_MASK" in source
    assert "WHEEL_BUTTONS = (4, 5)" in source


def test_atomic_window_integrates_bridge_and_runtime_snapshots() -> None:
    init_source = inspect.getsource(atomic_gui.WorkspaceWindow.__init__)
    park_source = inspect.getsource(atomic_gui.WorkspaceWindow._park_workspace)
    close_source = inspect.getsource(atomic_gui.WorkspaceWindow._close)

    assert "BrowserWheelBridge" in init_source
    assert "_sync_wheel_bridge_routes" in init_source
    assert "_record_workspace_runtime_snapshot" in park_source
    assert "bridge.close" in close_source


def test_candidate_diagnostic_uses_verified_final_collector() -> None:
    script = Path("scripts/candidate-diagnose.sh").read_text(encoding="utf-8")

    assert issubclass(VerifiedBlackboxCollector, FinalBlackboxCollector)
    assert "triview_workspace.diagnostic_blackbox_verified" in script
    assert "--auto-launch" in script
    assert "--auto-stop-on-application-exit" in script
