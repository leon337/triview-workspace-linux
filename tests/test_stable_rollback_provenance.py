from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLLBACK = ROOT / "scripts" / "stable-rollback.sh"


def _write_release(path: Path, version: str) -> None:
    package = path / "src" / "triview_workspace"
    workspace = path / "config" / "workspaces"
    package.mkdir(parents=True)
    workspace.mkdir(parents=True)
    (path / "pyproject.toml").write_text(
        f'[project]\nname = "triview-workspace"\nversion = "{version}"\n',
        encoding="utf-8",
    )
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


def test_stable_rollback_records_exact_ref_for_launcher_and_audit(tmp_path: Path) -> None:
    home = tmp_path / "home"
    app_root = tmp_path / "app"
    backup_root = tmp_path / "backups"
    data_home = tmp_path / "data"
    state_home = tmp_path / "state"
    home.mkdir()
    (app_root / "releases").mkdir(parents=True)
    backup_root.mkdir()
    (data_home / "triview-workspace").mkdir(parents=True)

    current = app_root / "releases" / "1.0.0a3"
    _write_release(current, "1.0.0a3")
    (app_root / "current").symlink_to(current)
    backup = backup_root / "update-a2"
    _write_release(backup / "current", "1.0.0a2")
    expected_ref = "e" * 40

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(app_root),
            "TRIVIEW_BACKUP_ROOT": str(backup_root),
            "XDG_DATA_HOME": str(data_home),
            "XDG_STATE_HOME": str(state_home),
            "TRIVIEW_NONINTERACTIVE": "1",
            "TRIVIEW_STABLE_REF": expected_ref,
        }
    )

    subprocess.run(
        ["bash", str(ROLLBACK), "--backup", str(backup)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    active = json.loads(
        (app_root / "ACTIVE-CANDIDATE.json").read_text(encoding="utf-8")
    )
    assert active["version"] == "1.0.0a2"
    assert active["ref"] == expected_ref
    assert active["status"] == "stable-rollback-restored"

    restored = (app_root / "current").resolve()
    release_metadata = json.loads(
        (restored / "candidate-release.json").read_text(encoding="utf-8")
    )
    assert release_metadata["version"] == "1.0.0a2"
    assert release_metadata["resolved_sha"] == expected_ref
    assert release_metadata["source_ref"] == "v1.0.0a2"

    transactions = list(
        (state_home / "triview-workspace" / "transactions").glob(
            "*-stable-rollback.json"
        )
    )
    reports = list(
        (state_home / "triview-workspace" / "stable-rollback-reports").glob(
            "*-rollback.json"
        )
    )
    assert len(transactions) == 1
    assert len(reports) == 1
    assert json.loads(transactions[0].read_text(encoding="utf-8"))["ref"] == expected_ref
    assert json.loads(reports[0].read_text(encoding="utf-8"))["ref"] == expected_ref
