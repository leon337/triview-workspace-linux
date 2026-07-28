from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLLBACK = ROOT / "scripts" / "candidate-rollback.sh"


def _write_release(path: Path, sha: str) -> None:
    path.mkdir(parents=True)
    (path / ".installed").touch()
    (path / "candidate-release.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "candidate_id": "TEST",
                "resolved_sha": sha,
                "module": "fake.module",
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_rollback_atomically_swaps_code_and_preserves_later_data(
    tmp_path: Path,
) -> None:
    app_root = tmp_path / "app"
    data_root = tmp_path / "data"
    state_root = tmp_path / "state"
    releases = app_root / "releases"
    current_release = releases / "current-release"
    previous_release = releases / "previous-release"
    current_sha = "a" * 40
    previous_sha = "b" * 40

    _write_release(current_release, current_sha)
    _write_release(previous_release, previous_sha)
    data_root.mkdir(parents=True)
    state_root.mkdir(parents=True)
    preserved = data_root / "workspace.json"
    preserved.write_text('{"version": 2}\n', encoding="utf-8")
    (app_root / "current").symlink_to(current_release)
    (app_root / "previous").symlink_to(previous_release)

    env = os.environ.copy()
    env["TRIVIEW_NONINTERACTIVE"] = "1"
    subprocess.run(
        [
            "bash",
            str(ROLLBACK),
            "TEST",
            str(app_root),
            str(data_root),
            str(state_root),
            "fake.module",
        ],
        check=True,
        text=True,
        env=env,
    )

    assert (app_root / "current").resolve() == previous_release.resolve()
    assert (app_root / "previous").resolve() == current_release.resolve()
    assert preserved.read_text(encoding="utf-8") == '{"version": 2}\n'

    backup_manifests = list(
        (state_root / "triview-workspace" / "backups").glob(
            "*/backup.json"
        )
    )
    assert len(backup_manifests) == 1
    backup = json.loads(backup_manifests[0].read_text(encoding="utf-8"))
    assert backup["verified"] is True
    assert backup["restore_policy"] == "manual-explicit-only"

    reports = list(
        (state_root / "triview-workspace" / "rollback-reports").glob(
            "*-rollback.json"
        )
    )
    assert len(reports) == 1
    report = json.loads(reports[0].read_text(encoding="utf-8"))
    assert report["old_sha"] == current_sha
    assert report["restored_sha"] == previous_sha
    assert report["data_restored"] is False
    assert report["atomic_exchange"] is True
