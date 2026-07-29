from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _bootstrap_scripts(tmp_path: Path, core_body: str) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in (
        "update.sh",
        "stable-launch.sh",
        "stable-diagnose.sh",
        "stable-rollback.sh",
    ):
        target = scripts / name
        target.write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")
        target.chmod(0o755)
    core = scripts / "update-core.sh"
    core.write_text(core_body, encoding="utf-8")
    core.chmod(0o755)
    return scripts


def _successful_stable_core() -> str:
    return """#!/usr/bin/env bash
set -Eeuo pipefail
script_dir="$(dirname "$(readlink -f "$0")")"
release="$TRIVIEW_APP_ROOT/releases/1.0.0a3"
mkdir -p "$release/scripts" "$TRIVIEW_APP_ROOT"
for name in update.sh update-core.sh stable-launch.sh stable-diagnose.sh stable-rollback.sh; do
  cp -a "$script_dir/$name" "$release/scripts/$name"
done
printf '1.0.0a3\n' > "$TRIVIEW_APP_ROOT/VERSION"
printf 'stable\n' > "$TRIVIEW_APP_ROOT/UPDATE_CHANNEL"
printf '{"schema_version": 1, "ref": ""}\n' > "$TRIVIEW_APP_ROOT/ACTIVE-CANDIDATE.json"
temporary="$TRIVIEW_APP_ROOT/.current-ref-test"
ln -s "$release" "$temporary"
mv -Tf "$temporary" "$TRIVIEW_APP_ROOT/current"
"""


def test_stable_update_refuses_to_replace_code_while_the_app_lock_is_held(
    tmp_path: Path,
) -> None:
    scripts = _bootstrap_scripts(tmp_path, "#!/usr/bin/env bash\nexit 99\n")
    home = tmp_path / "home"
    home.mkdir()
    state_home = tmp_path / "state"
    lock_dir = state_home / "triview-workspace"
    lock_dir.mkdir(parents=True)
    app_lock = lock_dir / "app.lock"
    ready = tmp_path / "app-ready"
    holder = subprocess.Popen(
        [
            "flock",
            str(app_lock),
            "bash",
            "-c",
            'touch "$1"; sleep 30',
            "holder",
            str(ready),
        ],
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists()
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "TRIVIEW_APP_ROOT": str(tmp_path / "app"),
                "XDG_STATE_HOME": str(state_home),
            }
        )
        completed = subprocess.run(
            ["bash", str(scripts / "update.sh"), "--stable", "--dry-run"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 3
        assert "feche o TriView Workspace" in (completed.stdout + completed.stderr)
    finally:
        if holder.poll() is None:
            os.killpg(holder.pid, signal.SIGTERM)
            holder.wait(timeout=5)


def test_stable_update_records_the_immutable_tag_sha_in_both_metadata_formats(
    tmp_path: Path,
) -> None:
    scripts = _bootstrap_scripts(tmp_path, _successful_stable_core())
    home = tmp_path / "home"
    home.mkdir()
    expected_sha = "c" * 40
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(tmp_path / "app"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "TRIVIEW_STABLE_REF": expected_sha,
            "TRIVIEW_NO_PAUSE": "1",
            "TRIVIEW_NO_RESULT_UI": "1",
        }
    )

    subprocess.run(
        ["bash", str(scripts / "update.sh"), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    app_root = tmp_path / "app"
    metadata = json.loads(
        (app_root / "ACTIVE-CANDIDATE.json").read_text(encoding="utf-8")
    )
    assert metadata["channel"] == "stable"
    assert metadata["candidate_id"] == "stable"
    assert metadata["version"] == "1.0.0a3"
    assert metadata["ref"] == expected_sha
    assert metadata["module"] == "triview_workspace.cli"
    assert metadata["status"] == "stable-release"

    release_metadata = json.loads(
        ((app_root / "current").resolve() / "candidate-release.json").read_text(
            encoding="utf-8"
        )
    )
    assert release_metadata["resolved_sha"] == expected_sha
    assert release_metadata["source_ref"] == "v1.0.0a3"
    assert release_metadata["module"] == "triview_workspace.cli"
    assert release_metadata["status"] == "stable-release"


def test_tag_lookup_failure_keeps_new_release_controllers_and_marks_ref_unresolved(
    tmp_path: Path,
) -> None:
    scripts = _bootstrap_scripts(tmp_path, _successful_stable_core())
    home = tmp_path / "home"
    home.mkdir()
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text("#!/usr/bin/env bash\nexit 22\n", encoding="utf-8")
    fake_curl.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(tmp_path / "app"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "TRIVIEW_NO_PAUSE": "1",
            "TRIVIEW_NO_RESULT_UI": "1",
            "PATH": f"{fake_bin}:{env['PATH']}",
        }
    )

    completed = subprocess.run(
        ["bash", str(scripts / "update.sh"), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    app_root = tmp_path / "app"
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

    metadata = json.loads(
        (app_root / "ACTIVE-CANDIDATE.json").read_text(encoding="utf-8")
    )
    assert metadata["version"] == "1.0.0a3"
    assert metadata["ref"] == ""
    assert metadata["status"] == "stable-release-ref-unresolved"
    assert "código e controladores permanecem ativos" in completed.stderr
