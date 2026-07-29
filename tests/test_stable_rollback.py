from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLLBACK = ROOT / "scripts" / "stable-rollback.sh"


def _write_release(path: Path, version: str, marker: str) -> None:
    package = path / "src" / "triview_workspace"
    workspace = path / "config" / "workspaces"
    package.mkdir(parents=True)
    workspace.mkdir(parents=True)
    (path / "pyproject.toml").write_text(
        f'[project]\nname = "triview-workspace"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (path / "marker.txt").write_text(marker, encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text(
        """from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--workspace")
    parser.add_argument("--data-file")
    parser.parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
        encoding="utf-8",
    )
    (workspace / "three-mobile.json").write_text("{}\n", encoding="utf-8")


def _environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path, Path, Path]:
    home = tmp_path / "home"
    app_root = tmp_path / "app"
    backup_root = tmp_path / "backups"
    data_root = tmp_path / "data"
    state_root = tmp_path / "state"
    home.mkdir()
    (app_root / "releases").mkdir(parents=True)
    backup_root.mkdir()
    (data_root / "triview-workspace").mkdir(parents=True)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(app_root),
            "TRIVIEW_BACKUP_ROOT": str(backup_root),
            "XDG_DATA_HOME": str(data_root),
            "XDG_STATE_HOME": str(state_root),
            "TRIVIEW_NONINTERACTIVE": "1",
        }
    )
    return env, app_root, backup_root, data_root, state_root


def test_stable_rollback_restores_backup_and_preserves_current_user_data(
    tmp_path: Path,
) -> None:
    env, app_root, backup_root, data_root, state_root = _environment(tmp_path)
    current_release = app_root / "releases" / "1.0.0a2-stable"
    _write_release(current_release, "1.0.0a2", "current")
    (app_root / "current").symlink_to(current_release)

    selected_backup = backup_root / "update-accepted"
    _write_release(selected_backup / "current", "1.0.0a1", "previous")
    catalog = data_root / "triview-workspace" / "workspaces.json"
    catalog.write_text('{"preserve": true}\n', encoding="utf-8")

    subprocess.run(
        ["bash", str(ROLLBACK), "--backup", str(selected_backup)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    restored_target = (app_root / "current").resolve()
    assert restored_target.parent == app_root / "releases"
    assert (restored_target / "marker.txt").read_text(encoding="utf-8") == "previous"
    assert (app_root / "VERSION").read_text(encoding="utf-8").strip() == "1.0.0a1"
    assert (app_root / "UPDATE_CHANNEL").read_text(encoding="utf-8").strip() == "stable"
    assert catalog.read_text(encoding="utf-8") == '{"preserve": true}\n'

    pre_backups = sorted(backup_root.glob("rollback-*"))
    assert len(pre_backups) == 1
    assert (pre_backups[0] / "current" / "marker.txt").read_text(encoding="utf-8") == "current"
    assert (pre_backups[0] / "workspaces.json").read_text(encoding="utf-8") == '{"preserve": true}\n'

    reports = sorted(
        (state_root / "triview-workspace" / "stable-rollback-reports").glob("*.json")
    )
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["event"] == "stable_rollback_committed"
    assert report["data_restored"] is False
    assert report["data_policy"] == "preserve-current-user-data"
    assert report["atomic_current_switch"] is True

    subprocess.run(
        ["bash", str(ROLLBACK)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert ((app_root / "current").resolve() / "marker.txt").read_text(
        encoding="utf-8"
    ) == "current"
    assert catalog.read_text(encoding="utf-8") == '{"preserve": true}\n'


def test_stable_rollback_rejects_backup_outside_controlled_root(tmp_path: Path) -> None:
    env, app_root, backup_root, _data_root, _state_root = _environment(tmp_path)
    current_release = app_root / "releases" / "current"
    _write_release(current_release, "1.0.0a2", "current")
    (app_root / "current").symlink_to(current_release)

    outside = tmp_path / "outside"
    _write_release(outside / "current", "1.0.0a1", "outside")

    completed = subprocess.run(
        ["bash", str(ROLLBACK), "--backup", str(outside)],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "nenhum backup restaurável" in (completed.stdout + completed.stderr)
    assert (app_root / "current").resolve() == current_release
    assert not list(backup_root.glob("rollback-*"))


def test_stable_rollback_dry_run_validates_without_mutation(tmp_path: Path) -> None:
    env, app_root, backup_root, data_root, state_root = _environment(tmp_path)
    current_release = app_root / "releases" / "current"
    _write_release(current_release, "1.0.0a2", "current")
    (app_root / "current").symlink_to(current_release)

    selected_backup = backup_root / "update-accepted"
    _write_release(selected_backup / "current", "1.0.0a1", "previous")
    catalog = data_root / "triview-workspace" / "workspaces.json"
    catalog.write_text('{"preserve": true}\n', encoding="utf-8")

    completed = subprocess.run(
        [
            "bash",
            str(ROLLBACK),
            "--backup",
            str(selected_backup),
            "--dry-run",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "DRY-RUN concluído" in completed.stdout
    assert (app_root / "current").resolve() == current_release
    assert not list(backup_root.glob("rollback-*"))
    assert not list((app_root / "releases").glob("*stable-rollback-*"))
    assert not (app_root / "VERSION").exists()
    assert catalog.read_text(encoding="utf-8") == '{"preserve": true}\n'
    assert not list(
        (state_root / "triview-workspace" / "stable-rollback-reports").glob("*.json")
    )


def test_update_controller_installs_official_stable_rollback_shortcut() -> None:
    text = (ROOT / "scripts" / "update.sh").read_text(encoding="utf-8")

    assert 'ROLLBACK_SOURCE="$SCRIPT_DIR/stable-rollback.sh"' in text
    assert 'TARGET_ROLLBACK="$UPDATER_ROOT/stable-rollback.sh"' in text
    assert 'ROLLBACK_LAUNCHER="$HOME/.local/bin/triview-workspace-rollback"' in text
    assert "Restaurar TriView Workspace" in text
    assert "metadata::trusted true" in text
