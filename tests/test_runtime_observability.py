from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import triview_workspace.runtime_observability as observability


def _configure_runtime(monkeypatch: Any, tmp_path: Path) -> tuple[Path, Path]:
    runtime = tmp_path / "release"
    state = tmp_path / "state"
    runtime.mkdir()
    (runtime / "candidate-release.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "resolved_sha": "a" * 40,
                "module": "triview_workspace.gui",
                "update_ref": "feat/triview-rc4-approved-ui",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TRIVIEW_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("TRIVIEW_RUNTIME_SHA", "a" * 40)
    monkeypatch.setenv("TRIVIEW_RUNTIME_MODULE", "triview_workspace.gui")
    monkeypatch.setenv("XDG_STATE_HOME", str(state))
    return runtime, state


def test_runtime_snapshot_records_exact_root_sha_module_and_backend(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    runtime, state = _configure_runtime(monkeypatch, tmp_path)

    path = observability.write_runtime_snapshot(
        module_name="triview_workspace.gui",
        backend_name="AtomicX11BraveBrowserBackend",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path == state / "triview-workspace" / "runtime-provenance.json"
    assert payload["runtime_root"] == str(runtime.resolve())
    assert payload["runtime_sha_env"] == "a" * 40
    assert payload["runtime_module_env"] == "triview_workspace.gui"
    assert payload["candidate_metadata"]["resolved_sha"] == "a" * 40
    assert payload["backend_name"] == "AtomicX11BraveBrowserBackend"
    assert payload["module_origin"].endswith("triview_workspace/gui.py")


def test_runtime_event_is_append_only_jsonl_with_candidate_identity(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    runtime, state = _configure_runtime(monkeypatch, tmp_path)

    path = observability.record_runtime_event(
        "browser_reparent_attempt",
        panel_id="chatgpt",
        host_window_id=900,
        parent_after=123,
        confirmed=False,
    )
    observability.record_runtime_event("browser_launch_failed", panel_id="chatgpt")

    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert path == state / "triview-workspace" / "runtime-events.jsonl"
    assert first["runtime_root"] == str(runtime.resolve())
    assert first["runtime_sha"] == "a" * 40
    assert first["event"] == "browser_reparent_attempt"
    assert first["host_window_id"] == 900
    assert first["parent_after"] == 123
    assert first["confirmed"] is False
    assert second["event"] == "browser_launch_failed"


def test_diagnostic_report_is_written_as_text_and_json(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    runtime, state = _configure_runtime(monkeypatch, tmp_path)
    monkeypatch.setattr(
        observability,
        "_command_report",
        lambda command, timeout=5.0: {
            "command": command,
            "available": True,
            "returncode": 0,
            "stdout": "ok\n",
            "stderr": "",
        },
    )

    text_path, json_path = observability.write_diagnostic_report()
    report = json.loads(json_path.read_text(encoding="utf-8"))
    text = text_path.read_text(encoding="utf-8")

    expected_dir = state / "triview-workspace" / "diagnostics"
    assert text_path.parent == expected_dir
    assert json_path.parent == expected_dir
    assert report["identity"]["runtime_root"] == str(runtime.resolve())
    assert report["identity"]["candidate_metadata"]["resolved_sha"] == "a" * 40
    assert "TRIVIEW WORKSPACE — RELATÓRIO DE DIAGNÓSTICO" in text
    assert "SHA instalado: " + "a" * 40 in text
