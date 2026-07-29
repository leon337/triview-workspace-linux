from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "update-channels" / "testing.json"
UPDATER = ROOT / "scripts" / "update.sh"
CORE = ROOT / "scripts" / "update-core.sh"
ROLLBACK = ROOT / "scripts" / "stable-rollback.sh"
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-bootstrap-release.yml"


def _wrapper_fixture(
    tmp_path: Path,
    core_body: str = "#!/usr/bin/env bash\nprintf 'ARGS:%s\\n' \"$*\"\n",
) -> tuple[Path, Path]:
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    wrapper = script_dir / "update.sh"
    core = script_dir / "update-core.sh"
    rollback = script_dir / "stable-rollback.sh"
    wrapper.write_text(UPDATER.read_text(encoding="utf-8"), encoding="utf-8")
    core.write_text(core_body, encoding="utf-8")
    rollback.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    core.chmod(0o755)
    rollback.chmod(0o755)
    return wrapper, core


def _wrapper_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "TRIVIEW_APP_ROOT": str(tmp_path / "app"),
            "TRIVIEW_NO_RESULT_UI": "1",
        }
    )
    return env


def test_repository_testing_manifest_is_archived_and_disabled() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert data["schema_version"] == 1
    assert data["channel"] == "testing"
    assert data["enabled"] is False
    assert data["candidate_id"] == "LEA-197"
    assert data["version"] == "0.3.3"
    assert data["status"] == "archived-after-1.0.0a1-release"
    assert re.fullmatch(r"[0-9a-f]{40}", data["ref"])


def test_wrapper_defaults_to_stable_without_explicit_choice(tmp_path: Path) -> None:
    wrapper, _core = _wrapper_fixture(tmp_path)
    completed = subprocess.run(
        ["bash", str(wrapper), "--dry-run"],
        env=_wrapper_env(tmp_path),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ARGS:--stable --dry-run" in completed.stdout


def test_wrapper_preserves_explicit_testing_argument(tmp_path: Path) -> None:
    wrapper, _core = _wrapper_fixture(tmp_path)
    completed = subprocess.run(
        ["bash", str(wrapper), "--testing", "--dry-run"],
        env=_wrapper_env(tmp_path),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ARGS:--testing --dry-run" in completed.stdout
    assert "--stable" not in completed.stdout


def test_wrapper_honors_environment_channel(tmp_path: Path) -> None:
    wrapper, _core = _wrapper_fixture(tmp_path)
    env = _wrapper_env(tmp_path)
    env["TRIVIEW_UPDATE_CHANNEL"] = "testing"
    completed = subprocess.run(
        ["bash", str(wrapper), "--dry-run"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ARGS:--dry-run" in completed.stdout
    assert "--stable" not in completed.stdout


def test_wrapper_honors_persisted_channel(tmp_path: Path) -> None:
    wrapper, _core = _wrapper_fixture(tmp_path)
    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "UPDATE_CHANNEL").write_text("testing\n", encoding="utf-8")
    completed = subprocess.run(
        ["bash", str(wrapper), "--dry-run"],
        env=_wrapper_env(tmp_path),
        check=True,
        capture_output=True,
        text=True,
    )

    assert "ARGS:--dry-run" in completed.stdout
    assert "--stable" not in completed.stdout


def test_wrapper_reinstalls_itself_and_second_run_is_idempotent(tmp_path: Path) -> None:
    wrapper, core = _wrapper_fixture(tmp_path, "#!/usr/bin/env bash\nexit 0\n")
    app_root = tmp_path / "app"
    env = _wrapper_env(tmp_path)
    subprocess.run(
        ["bash", str(wrapper), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    persistent_wrapper = app_root / "updater" / "update.sh"
    persistent_core = app_root / "updater" / "update-core.sh"
    persistent_rollback = app_root / "updater" / "stable-rollback.sh"
    assert persistent_wrapper.read_text(encoding="utf-8") == wrapper.read_text(
        encoding="utf-8"
    )
    assert persistent_core.read_text(encoding="utf-8") == core.read_text(
        encoding="utf-8"
    )
    assert persistent_rollback.is_file()
    assert (tmp_path / "home" / ".local" / "bin" / "triview-workspace-rollback").is_file()

    subprocess.run(
        ["bash", str(persistent_wrapper), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert persistent_wrapper.is_file()
    assert persistent_core.is_file()
    assert persistent_rollback.is_file()


def test_disabled_repository_manifest_blocks_explicit_testing(tmp_path: Path) -> None:
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
        ["bash", str(CORE), "--testing", "--dry-run"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "canal de testes bloqueado" in (completed.stdout + completed.stderr)


def test_explicit_testing_accepts_only_enabled_temporary_manifest(tmp_path: Path) -> None:
    enabled_manifest = tmp_path / "testing-enabled.json"
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data["enabled"] = True
    data["status"] = "test-fixture-enabled"
    enabled_manifest.write_text(json.dumps(data), encoding="utf-8")

    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(tmp_path / "app"),
            "TRIVIEW_BACKUP_ROOT": str(tmp_path / "backups"),
            "TRIVIEW_TEST_MANIFEST_FILE": str(enabled_manifest),
            "TRIVIEW_NO_RESULT_UI": "1",
        }
    )

    completed = subprocess.run(
        ["bash", str(CORE), "--testing", "--dry-run"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Candidato autorizado: LEA-197" in completed.stdout
    assert data["ref"] in completed.stdout
    assert "/archive/refs/heads/main.tar.gz" not in completed.stdout
    assert not (tmp_path / "app" / "current").exists()


def test_updater_repairs_desktop_shortcuts_and_shows_result() -> None:
    text = CORE.read_text(encoding="utf-8")

    assert 'UPDATER_ROOT="$APP_ROOT/updater"' in text
    assert 'applications_dir="$HOME/.local/share/applications"' in text
    assert "xdg-user-dir DESKTOP" in text
    assert '"$HOME/Área de Trabalho"' in text
    assert "Atualizar TriView Workspace.desktop" in text
    assert "grep -Eq" in text
    assert 'gio set "$file" metadata::trusted true' in text
    assert "x-terminal-emulator" in text
    assert 'zenity "$icon"' in text
    assert "TRIVIEW_UPDATER_WRAPPED=1" in text
    assert 'tee -a "\\$LOG_FILE"' in text
    assert "PIPESTATUS[0]" in text
    assert "Pressione ENTER para fechar esta janela" in text
    assert "ATUALIZAÇÃO FINALIZADA COM SUCESSO" in text


def test_application_desktop_entry_uses_standard_directory() -> None:
    text = CORE.read_text(encoding="utf-8")

    assert 'APPLICATIONS_DIR="$HOME/.local/share/applications"' in text
    assert "$HOME/.local/applications" not in text


def test_release_publication_waits_for_complete_verification() -> None:
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")

    assert "verify:" in text
    assert "release:\n    needs: verify" in text
    assert "pytest --junitxml=release-pytest-results.xml" in text
    assert "tests/test_browser_wheel_x11_integration.py" in text
    assert "XTEST pointer" in text
    assert "tests/test_browser_xephyr_x11_integration.py" in text
    assert "bash -n scripts/*.sh packaging/*.sh" in text
    assert "gh release create" in text
    assert '"scripts/stable-rollback.sh"' in text
