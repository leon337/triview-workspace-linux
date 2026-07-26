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
    assert data["version"] == "0.3.3"
    assert data["module"] == "triview_workspace.cli"
    assert data["status"] == "updater-desktop-shortcut-hotfix"
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
            "TRIVIEW_NO_RESULT_UI": "1",
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
    assert "atalho antigo da Área de Trabalho seria substituído" in output
    assert "janela gráfica" in output
    assert not (tmp_path / "app" / "current").exists()


def test_updater_repairs_desktop_shortcuts_and_shows_result() -> None:
    text = UPDATER.read_text(encoding="utf-8")

    assert 'UPDATER_ROOT="$APP_ROOT/updater"' in text
    assert 'applications_dir="$HOME/.local/share/applications"' in text
    assert 'xdg-user-dir DESKTOP' in text
    assert '"$HOME/Área de Trabalho"' in text
    assert 'Atualizar TriView Workspace.desktop' in text
    assert 'grep -Eq' in text
    assert 'gio set "$file" metadata::trusted true' in text
    assert 'x-terminal-emulator' in text
    assert 'zenity "$icon"' in text
    assert 'TRIVIEW_UPDATER_WRAPPED=1' in text
    assert 'tee -a "\\$LOG_FILE"' in text
    assert "PIPESTATUS[0]" in text
    assert "Pressione ENTER para fechar esta janela" in text
    assert "ATUALIZAÇÃO FINALIZADA COM SUCESSO" in text


def test_application_desktop_entry_uses_standard_directory() -> None:
    text = UPDATER.read_text(encoding="utf-8")

    assert 'APPLICATIONS_DIR="$HOME/.local/share/applications"' in text
    assert '$HOME/.local/applications' not in text
