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
STABLE_LAUNCH = ROOT / "scripts" / "stable-launch.sh"
STABLE_DIAGNOSE = ROOT / "scripts" / "stable-diagnose.sh"
ROLLBACK = ROOT / "scripts" / "stable-rollback.sh"
PUBLISH_WORKFLOW = ROOT / ".github" / "workflows" / "publish-bootstrap-release.yml"


def _successful_core_body() -> str:
    return """#!/usr/bin/env bash
set -Eeuo pipefail
script_dir="$(dirname "$(readlink -f "$0")")"
release="$TRIVIEW_APP_ROOT/releases/fake-stable"
mkdir -p "$release/scripts" "$TRIVIEW_APP_ROOT"
for name in update.sh update-core.sh stable-launch.sh stable-diagnose.sh stable-rollback.sh; do
  cp -a "$script_dir/$name" "$release/scripts/$name"
done
temporary="$TRIVIEW_APP_ROOT/.current-test"
rm -f "$temporary"
ln -s "$release" "$temporary"
mv -Tf "$temporary" "$TRIVIEW_APP_ROOT/current"
printf 'ARGS:%s\n' "$*"
"""


def _wrapper_fixture(
    tmp_path: Path,
    core_body: str = "#!/usr/bin/env bash\nprintf 'ARGS:%s\\n' \"$*\"\n",
) -> tuple[Path, Path]:
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    wrapper = script_dir / "update.sh"
    core = script_dir / "update-core.sh"
    stable_launch = script_dir / "stable-launch.sh"
    stable_diagnose = script_dir / "stable-diagnose.sh"
    rollback = script_dir / "stable-rollback.sh"
    wrapper.write_text(UPDATER.read_text(encoding="utf-8"), encoding="utf-8")
    core.write_text(core_body, encoding="utf-8")
    stable_launch.write_text(STABLE_LAUNCH.read_text(encoding="utf-8"), encoding="utf-8")
    stable_diagnose.write_text(STABLE_DIAGNOSE.read_text(encoding="utf-8"), encoding="utf-8")
    rollback.write_text(ROLLBACK.read_text(encoding="utf-8"), encoding="utf-8")
    for path in (wrapper, core, stable_launch, stable_diagnose, rollback):
        path.chmod(0o755)
    return wrapper, core


def _wrapper_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "TRIVIEW_APP_ROOT": str(tmp_path / "app"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "TRIVIEW_NO_RESULT_UI": "1",
            "TRIVIEW_NO_PAUSE": "1",
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


def test_wrapper_installs_release_owned_suite_and_four_shortcuts_idempotently(
    tmp_path: Path,
) -> None:
    wrapper, _core = _wrapper_fixture(tmp_path, _successful_core_body())
    home = tmp_path / "home"
    desktop = home / "Desktop"
    desktop.mkdir(parents=True)
    app_root = tmp_path / "app"
    env = _wrapper_env(tmp_path)

    subprocess.run(
        ["bash", str(wrapper), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    persistent = app_root / "updater"
    active_scripts = (app_root / "current").resolve() / "scripts"
    for name in (
        "update.sh",
        "update-core.sh",
        "stable-launch.sh",
        "stable-diagnose.sh",
        "stable-rollback.sh",
    ):
        assert (persistent / name).read_text(encoding="utf-8") == (
            active_scripts / name
        ).read_text(encoding="utf-8")
        assert os.access(persistent / name, os.X_OK)

    bin_dir = home / ".local" / "bin"
    for name in (
        "triview-workspace",
        "triview-workspace-update",
        "triview-workspace-diagnose",
        "triview-workspace-rollback",
    ):
        assert (bin_dir / name).is_file()
        assert os.access(bin_dir / name, os.X_OK)

    applications = home / ".local" / "share" / "applications"
    application_entries = {
        "triview-workspace.desktop": "Name=TriView Workspace",
        "triview-workspace-update.desktop": "Name=Atualizar TriView Workspace",
        "triview-workspace-diagnose.desktop": "Name=Diagnosticar TriView Workspace",
        "triview-workspace-rollback.desktop": "Name=Restaurar TriView Workspace",
    }
    for filename, expected_name in application_entries.items():
        text = (applications / filename).read_text(encoding="utf-8")
        assert expected_name in text

    for visible_name in (
        "TriView Workspace",
        "Atualizar TriView Workspace",
        "Diagnosticar TriView Workspace",
        "Restaurar TriView Workspace",
    ):
        assert (desktop / f"{visible_name}.desktop").is_file()

    persistent_wrapper = persistent / "update.sh"
    subprocess.run(
        ["bash", str(persistent_wrapper), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    for name in (
        "update.sh",
        "update-core.sh",
        "stable-launch.sh",
        "stable-diagnose.sh",
        "stable-rollback.sh",
    ):
        assert (persistent / name).is_file()
        assert os.access(persistent / name, os.X_OK)


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


def test_legacy_core_result_ui_and_shortcut_compatibility_remain_available() -> None:
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


def test_stable_controller_uses_standard_directories_and_release_owned_scripts() -> None:
    text = UPDATER.read_text(encoding="utf-8")

    assert 'APPLICATIONS_DIR="$HOME/.local/share/applications"' in text
    assert "$HOME/.local/applications" not in text
    assert 'ACTIVE_SCRIPTS="$CURRENT_TARGET/scripts"' in text
    assert "stable-launch.sh" in text
    assert "stable-diagnose.sh" in text
    assert "stable-rollback.sh" in text
    assert "Diagnosticar TriView Workspace" in text
    assert "Restaurar TriView Workspace" in text


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
    for path in (
        "scripts/stable-launch.sh",
        "scripts/stable-diagnose.sh",
        "scripts/stable-rollback.sh",
    ):
        assert f'"{path}"' in text
