from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "update-channels" / "testing.json"
UPDATER = ROOT / "scripts" / "update.sh"


def test_testing_manifest_is_valid_and_targets_lea_197() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["channel"] == "testing"
    assert data["enabled"] is True
    assert data["candidate_id"] == "LEA-197"
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", data["version"])
    assert data["module"] == "triview_workspace.cli"
    assert isinstance(data["status"], str) and data["status"]
    assert re.fullmatch(r"[0-9a-f]{40}", data["ref"])


def test_updater_dry_run_resolves_only_the_authorized_candidate(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(tmp_path / "app"),
            "TRIVIEW_BACKUP_ROOT": str(tmp_path / "backups"),
            "TRIVIEW_TEST_MANIFEST_FILE": str(MANIFEST),
        }
    )

    completed = subprocess.run(
        ["bash", str(UPDATER), "--dry-run"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    output = completed.stdout
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "Candidato autorizado: LEA-197" in output
    assert data["ref"] in output
    assert "/archive/refs/heads/main.tar.gz" not in output
    assert "mantido na tela e salvo em log" in output
    assert not (tmp_path / "app" / "current").exists()


def test_updater_keeps_result_visible_and_saves_a_log() -> None:
    text = UPDATER.read_text(encoding="utf-8")

    assert 'UPDATER_ROOT="$APP_ROOT/updater"' in text
    assert 'target_script="$UPDATER_ROOT/update.sh"' in text
    assert 'tee -a "\\$LOG_FILE"' in text
    assert "PIPESTATUS[0]" in text
    assert "Pressione ENTER para fechar esta janela" in text
    assert "ATUALIZAÇÃO FINALIZADA COM SUCESSO" in text
