from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "candidate-launch.sh"
UPDATER = ROOT / "scripts" / "candidate-update.sh"
DIAGNOSTIC = ROOT / "scripts" / "candidate-diagnose.sh"


@pytest.mark.parametrize("script", [LAUNCHER, UPDATER, DIAGNOSTIC])
def test_runtime_scripts_keep_valid_bash_syntax(script: Path) -> None:
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_launcher_enforces_one_candidate_instance() -> None:
    script = LAUNCHER.read_text(encoding="utf-8")

    assert 'LOCK_FILE="$APP_STATE/app.lock"' in script
    assert 'PID_FILE="$APP_STATE/app.pid"' in script
    assert "flock -n 9" in script
    assert "existing_instance_activated" in script
    assert "xdotool windowactivate" in script


def test_updater_refuses_to_replace_runtime_while_candidate_is_open() -> None:
    script = UPDATER.read_text(encoding="utf-8")

    assert 'UPDATE_LOCK="$APP_STATE/update.lock"' in script
    assert "flock -n 8" in script
    assert 'pathlib.Path("/proc").glob("[0-9]*/environ")' in script
    assert 'entries.get("TRIVIEW_RUNTIME_MODULE")' in script
    assert 'entries.get("TRIVIEW_RUNTIME_ROOT")' in script
    assert "Feche o TriView Workspace antes de atualizar" in script


def test_successful_diagnostic_includes_raw_runtime_evidence() -> None:
    script = DIAGNOSTIC.read_text(encoding="utf-8")

    assert 'PROVENANCE="$APP_STATE/runtime-provenance.json"' in script
    assert 'RUNTIME_EVENTS="$APP_STATE/runtime-events.jsonl"' in script
    assert 'tail -n 500 "$RUNTIME_EVENTS"' in script
    assert 'cat "$PROVENANCE"' in script
    assert "ÚLTIMOS EVENTOS DO RUNTIME" in script
