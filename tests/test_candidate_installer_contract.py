from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_INSTALLER = ROOT / "scripts" / "install-module-candidate.sh"
RC4_INSTALLER = ROOT / "scripts" / "install-train-candidate.sh"
CANDIDATE_LAUNCHER = ROOT / "scripts" / "candidate-launch.sh"
CANDIDATE_UPDATER = ROOT / "scripts" / "candidate-update.sh"
CANDIDATE_DIAGNOSTIC = ROOT / "scripts" / "candidate-diagnose.sh"
CANDIDATE_ROLLBACK = ROOT / "scripts" / "candidate-rollback.sh"


@pytest.mark.parametrize(
    "script",
    [
        MODULE_INSTALLER,
        RC4_INSTALLER,
        CANDIDATE_LAUNCHER,
        CANDIDATE_UPDATER,
        CANDIDATE_DIAGNOSTIC,
        CANDIDATE_ROLLBACK,
    ],
)
def test_candidate_installer_has_valid_bash_syntax(script: Path) -> None:
    subprocess.run(["bash", "-n", str(script)], check=True)


def test_module_installer_resolves_mutable_ref_to_immutable_sha() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    assert "https://api.github.com/repos/$REPO/commits/$encoded_ref" in script
    assert "RESOLVED_SHA" in script
    assert "archive/$RESOLVED_SHA.tar.gz" in script
    assert '[[ "$RESOLVED_SHA" =~ ^[0-9a-f]{40}$ ]]' in script


def test_module_installer_records_release_identity_and_previous_candidate() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    assert "candidate-release.json" in script
    assert '"resolved_sha": resolved_sha' in script
    assert '"update_ref": update_ref' in script
    assert 'previous_link="$APP_ROOT/previous"' in script
    assert 'mv -Tf "$current_temp" "$current_link"' in script


def test_module_installer_rejects_unsafe_archive_entries() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    assert "path.is_absolute()" in script
    assert '".." in path.parts' in script


def test_module_installer_creates_open_update_diagnostic_and_rollback_launchers() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    assert "candidate-launch.sh" in script
    assert "candidate-update.sh" in script
    assert "candidate-diagnose.sh" in script
    assert "candidate-rollback.sh" in script
    assert "Atualizar TriView Workspace" in script
    assert "Diagnosticar TriView Workspace" in script
    assert "Reverter TriView Workspace" in script
    assert "runtime_observability" in script


def test_module_installer_reconciles_idempotent_runs_and_verified_backup() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    assert "idempotent_update_reconciled" in script
    assert 'if [[ "$current_sha" == "$RESOLVED_SHA" ]]' in script
    assert "Reconciliando a instalação existente" in script
    assert "archive_pending_transactions" in script
    assert "reconciled_transactions" in script
    assert "SHA256SUMS" in script
    assert "sha256sum -c SHA256SUMS" in script
    assert '"verified": True' in script
    assert '"restore_policy": "manual-explicit-only"' in script


def test_module_installer_has_pre_and_post_switch_failpoints() -> None:
    script = MODULE_INSTALLER.read_text(encoding="utf-8")

    before_index = script.index("TRIVIEW_TEST_FAIL_BEFORE_SWITCH")
    current_switch_index = script.index('mv -Tf "$current_temp" "$current_link"')
    after_index = script.index("TRIVIEW_TEST_FAIL_AFTER_SWITCH")
    reconciliation_index = script.index(
        "# Reconciliation is intentionally common to new installs and idempotent reruns."
    )

    assert before_index < current_switch_index < after_index < reconciliation_index
    assert "Interrupção controlada antes da troca atômica" in script
    assert "Interrupção controlada depois da troca atômica" in script


def test_candidate_launcher_records_exact_runtime_before_exec() -> None:
    script = CANDIDATE_LAUNCHER.read_text(encoding="utf-8")

    assert "current_target=" in script
    assert "resolved_sha=" in script
    assert "TRIVIEW_RUNTIME_ROOT" in script
    assert "TRIVIEW_RUNTIME_SHA" in script
    assert "TRIVIEW_RUNTIME_MODULE" in script
    assert "launcher.log" in script
    assert "app.stderr.log" in script


def test_candidate_diagnostic_uses_sanitized_x11_process_and_runtime_collectors() -> None:
    script = CANDIDATE_DIAGNOSTIC.read_text(encoding="utf-8")

    assert "runtime_observability" in script
    assert "diagnostic_blackbox_shareable" in script
    assert "diagnostic_fallback_shareable" in script
    assert "runtime-events.jsonl" in script
    assert "candidate-release.json" in script
    assert "ps -eo pid,ppid,pgid,lstart,args" not in script
    assert "xwininfo -root -tree" not in script
    assert 'cat "$PROVENANCE"' not in script
    assert 'tail -n 500 "$RUNTIME_EVENTS"' not in script


def test_candidate_rollback_requires_atomic_exchange_and_preserves_data() -> None:
    script = CANDIDATE_ROLLBACK.read_text(encoding="utf-8")

    assert "RENAME_EXCHANGE = 2" in script
    assert "renameat2" in script
    assert '"data_restored": False' in script
    assert '"data_policy": "preserve-later-data"' in script
    assert '"atomic_exchange": True' in script
    assert "sha256sum -c SHA256SUMS" in script


def test_rc4_installer_requires_full_sha_and_opens_approved_gui() -> None:
    script = RC4_INSTALLER.read_text(encoding="utf-8")

    assert "TRIVIEW_CANDIDATE_REF" in script
    assert 'git -C "$REPO_ROOT" rev-parse HEAD' in script
    assert '[[ ! "$SOURCE_REF" =~ ^[0-9a-fA-F]{40}$ ]]' in script
    assert '"RC4-1.0.0A1"' in script
    assert '"triview_workspace.gui"' in script
    assert "train/road-to-1.0" not in script
    assert "triview_workspace.gui_hub" not in script
