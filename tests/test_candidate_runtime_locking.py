from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install-module-candidate.sh"
LAUNCHER = ROOT / "scripts" / "candidate-launch.sh"
UPDATER = ROOT / "scripts" / "candidate-update.sh"
DIAGNOSTIC = ROOT / "scripts" / "candidate-diagnose.sh"
ROLLBACK = ROOT / "scripts" / "candidate-rollback.sh"


@pytest.mark.parametrize(
    "script",
    [INSTALLER, LAUNCHER, UPDATER, DIAGNOSTIC, ROLLBACK],
)
def test_runtime_scripts_keep_valid_bash_syntax(script: Path) -> None:
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_launcher_enforces_one_candidate_instance() -> None:
    script = LAUNCHER.read_text(encoding="utf-8")

    assert 'LOCK_FILE="$APP_STATE/app.lock"' in script
    assert 'PID_FILE="$APP_STATE/app.pid"' in script
    assert "flock -n 9" in script
    assert "existing_instance_activated" in script
    assert "xdotool windowactivate" in script


def test_install_update_and_rollback_share_one_lifecycle_lock() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")
    updater = UPDATER.read_text(encoding="utf-8")
    rollback = ROLLBACK.read_text(encoding="utf-8")

    expected = 'LIFECYCLE_LOCK="$APP_STATE/lifecycle.lock"'
    assert expected in installer
    assert expected in updater
    assert expected in rollback
    assert "flock -n 9" in installer
    assert "flock -n 8" in updater
    assert "flock -n 8" in rollback
    assert "TRIVIEW_LIFECYCLE_LOCK_HELD=1" in updater
    assert "outra operação de instalação, atualização ou rollback" in installer
    assert "outra operação de instalação, atualização ou rollback" in updater
    assert "outra operação de instalação, atualização ou rollback" in rollback


def test_updater_refuses_to_replace_runtime_while_candidate_is_open() -> None:
    script = UPDATER.read_text(encoding="utf-8")

    assert 'pathlib.Path("/proc").glob("[0-9]*/environ")' in script
    assert 'entries.get("TRIVIEW_RUNTIME_MODULE")' in script
    assert 'entries.get("TRIVIEW_RUNTIME_ROOT")' in script
    assert "Feche o TriView Workspace antes de atualizar" in script


def test_successful_diagnostic_includes_sanitized_runtime_evidence() -> None:
    script = DIAGNOSTIC.read_text(encoding="utf-8")

    assert "diagnostic_blackbox_shareable" in script
    assert "diagnostic_fallback_shareable" in script
    assert "runtime_observability" in script
    assert "runtime-events.jsonl" in script
    assert "ÚLTIMOS EVENTOS DO RUNTIME" in script
    assert 'tail -n 500 "$RUNTIME_EVENTS"' not in script
    assert 'cat "$PROVENANCE"' not in script
