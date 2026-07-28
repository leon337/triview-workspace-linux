from __future__ import annotations

import json
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from triview_workspace.diagnostic_blackbox_shareable import (
    ShareableBlackboxCollector,
    parse_shareable_xinput_event,
)
from triview_workspace.diagnostic_fallback_shareable import (
    build_shareable_fallback,
)


def _runtime_record(monotonic_ns: int, **event: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    wrapped = {"monotonic_ns": monotonic_ns, "runtime_event": event}
    return wrapped, event


def test_shareable_xinput_keeps_one_wheel_release_with_x11_correlation() -> None:
    release = parse_shareable_xinput_event(
        [
            "EVENT type 16 (ButtonRelease)\n",
            "    detail: 5\n",
            "    time: 123456\n",
            "    event: 0x2a\n",
        ],
        safe_keymap={},
        pointer={"x": 10, "y": 20, "window": 42},
    )
    press = parse_shareable_xinput_event(
        [
            "EVENT type 15 (ButtonPress)\n",
            "    detail: 5\n",
            "    time: 123456\n",
        ],
        safe_keymap={},
        pointer={"x": 10, "y": 20, "window": 42},
    )
    raw = parse_shareable_xinput_event(
        [
            "EVENT type 13 (RawButtonRelease)\n",
            "    detail: 5\n",
            "    time: 123456\n",
        ],
        safe_keymap={},
        pointer={"x": 10, "y": 20, "window": 42},
    )

    assert release is not None
    assert release["input_category"] == "mouse_wheel"
    assert release["input_correlation_id"] == "wheel:123456:5"
    assert release["event_window_id"] == 42
    assert press is None
    assert raw is None


def test_scroll_finding_requires_exactly_one_delivery_per_input() -> None:
    inputs = [
        {
            "input_category": "mouse_wheel",
            "input_correlation_id": "wheel:100:5",
        }
    ]
    records = [
        _runtime_record(
            200,
            event="wheel_event_forwarded",
            input_correlation_id="wheel:100:5",
            runtime_id="agents::architect",
            host_window_id=900,
            browser_window_id="77",
            delivered=True,
        )
    ]

    finding = ShareableBlackboxCollector._correlated_scroll_finding(records, inputs)

    assert finding["status"] == "PASS_ONE_TO_ONE_X11_ROUTE"
    assert finding["failure_count"] == 0
    assert finding["matches"][0]["delivery_count"] == 1


def test_scroll_finding_rejects_loss_duplication_and_unmatched_delivery() -> None:
    inputs = [
        {
            "input_category": "mouse_wheel",
            "input_correlation_id": "wheel:100:5",
        },
        {
            "input_category": "mouse_wheel",
            "input_correlation_id": "wheel:101:5",
        },
    ]
    records = [
        _runtime_record(
            200,
            event="wheel_event_forwarded",
            input_correlation_id="wheel:100:5",
            runtime_id="agents::architect",
            host_window_id=900,
            browser_window_id="77",
            delivered=True,
        ),
        _runtime_record(
            201,
            event="wheel_event_forwarded",
            input_correlation_id="wheel:100:5",
            runtime_id="agents::architect",
            host_window_id=900,
            browser_window_id="77",
            delivered=True,
        ),
        _runtime_record(
            202,
            event="wheel_event_forwarded",
            input_correlation_id="wheel:999:5",
            runtime_id="social::youtube",
            host_window_id=901,
            browser_window_id="88",
            delivered=True,
        ),
    ]

    finding = ShareableBlackboxCollector._correlated_scroll_finding(records, inputs)

    assert finding["status"] == "FAIL_SCROLL_LOSS_DUPLICATION_OR_ROUTE"
    assert finding["failure_count"] == 3


def test_continuity_requires_pid_pgid_window_and_host() -> None:
    runtime = {
        "runtime_id": "agents::architect",
        "active": True,
        "pid": 101,
        "pgid": 101,
        "window_id": "77",
        "host_window_id": 900,
    }
    records = [
        _runtime_record(
            10,
            event="workspace_runtime_snapshot",
            phase="parked",
            workspace_id="agents",
            runtimes=[runtime],
        ),
        _runtime_record(
            30,
            event="workspace_runtime_snapshot",
            phase="restored",
            workspace_id="agents",
            runtimes=[runtime],
        ),
    ]

    finding = ShareableBlackboxCollector._strict_workspace_continuity_finding(records)

    assert finding["status"] == "PASS_SAME_PID_PGID_WINDOW_AND_HOST"
    assert finding["failure_count"] == 0


def test_continuity_fails_when_pgid_or_host_changes() -> None:
    before = {
        "runtime_id": "agents::architect",
        "active": True,
        "pid": 101,
        "pgid": 101,
        "window_id": "77",
        "host_window_id": 900,
    }
    after = {
        "runtime_id": "agents::architect",
        "active": True,
        "pid": 101,
        "pgid": 202,
        "window_id": "77",
        "host_window_id": 901,
    }
    records = [
        _runtime_record(
            10,
            event="workspace_runtime_snapshot",
            phase="parked",
            workspace_id="agents",
            runtimes=[before],
        ),
        _runtime_record(
            30,
            event="workspace_runtime_snapshot",
            phase="restored",
            workspace_id="agents",
            runtimes=[after],
        ),
    ]

    finding = ShareableBlackboxCollector._strict_workspace_continuity_finding(records)

    assert finding["status"] == "FAIL_RUNTIME_CHANGED_OR_RELAUNCHED"
    failure = finding["cycles"][0]["failures"][0]
    assert failure["same_pid"] is True
    assert failure["same_pgid"] is False
    assert failure["same_window_id"] is True
    assert failure["same_host_window_id"] is False


def test_sanitized_fallback_zip_contains_no_raw_private_values(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    xdg_state = tmp_path / "state-home"
    state = xdg_state / "triview-workspace"
    state.mkdir(parents=True)
    monkeypatch.setenv("XDG_STATE_HOME", str(xdg_state))
    (state / "runtime-provenance.json").write_text(
        json.dumps(
            {
                "cwd": "/home/leo/private/project",
                "runtime_root": "/home/leo/.local/private-runtime",
                "module_origin": "/home/leo/private/module.py",
                "url": "https://chatgpt.com/c/private-conversation?token=abc",
            }
        ),
        encoding="utf-8",
    )
    (state / "runtime-events.jsonl").write_text(
        json.dumps(
            {
                "event": "browser_launch_requested",
                "url": "https://github.com/private/repository/issues/1",
                "profile_dir": "/home/leo/.private-profile",
                "message_text": "do not export this",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (state / "launcher.log").write_text(
        "failed at /home/leo/private/path token=super-secret\n",
        encoding="utf-8",
    )

    package = build_shareable_fallback(
        tmp_path / "output",
        "failure at /home/leo/private/path token=super-secret",
    )

    with zipfile.ZipFile(package) as archive:
        exported = "\n".join(
            archive.read(name).decode("utf-8", errors="replace")
            for name in archive.namelist()
        )
    assert "/home/leo" not in exported
    assert "private-conversation" not in exported
    assert "private/repository" not in exported
    assert "super-secret" not in exported
    assert "do not export this" not in exported
    assert "[LOCAL_PATH]" in exported or "[REDACTED]" in exported


def test_candidate_diagnostic_never_runs_raw_fallback_commands() -> None:
    script = Path("scripts/candidate-diagnose.sh").read_text(encoding="utf-8")

    assert "diagnostic_blackbox_shareable" in script
    assert "diagnostic_fallback_shareable" in script
    assert "ps -eo pid,ppid,pgid,lstart,args" not in script
    assert "cat \"$PROVENANCE\"" not in script
    assert "tail -n 500 \"$RUNTIME_EVENTS\"" not in script
