from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "update.sh"
STABLE_LAUNCH = ROOT / "scripts" / "stable-launch.sh"
STABLE_DIAGNOSE = ROOT / "scripts" / "stable-diagnose.sh"
ROLLBACK = ROOT / "scripts" / "stable-rollback.sh"


def test_stable_update_and_rollback_refuse_the_same_held_lifecycle_lock(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    app_root = tmp_path / "app"
    state_home = tmp_path / "state"
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    home.mkdir()

    wrapper = scripts / "update.sh"
    core = scripts / "update-core.sh"
    stable_launch = scripts / "stable-launch.sh"
    stable_diagnose = scripts / "stable-diagnose.sh"
    rollback_source = scripts / "stable-rollback.sh"
    wrapper.write_text(UPDATER.read_text(encoding="utf-8"), encoding="utf-8")
    core.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    stable_launch.write_text(STABLE_LAUNCH.read_text(encoding="utf-8"), encoding="utf-8")
    stable_diagnose.write_text(STABLE_DIAGNOSE.read_text(encoding="utf-8"), encoding="utf-8")
    rollback_source.write_text(ROLLBACK.read_text(encoding="utf-8"), encoding="utf-8")
    for path in (wrapper, core, stable_launch, stable_diagnose, rollback_source):
        path.chmod(0o755)

    lock_dir = state_home / "triview-workspace"
    lock_dir.mkdir(parents=True)
    lock_file = lock_dir / "lifecycle.lock"
    ready = tmp_path / "lock-ready"
    holder = subprocess.Popen(
        [
            "flock",
            str(lock_file),
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
        assert ready.exists(), "lock holder did not start"

        env = os.environ.copy()
        env.update(
            {
                "HOME": str(home),
                "TRIVIEW_APP_ROOT": str(app_root),
                "TRIVIEW_BACKUP_ROOT": str(tmp_path / "backups"),
                "XDG_STATE_HOME": str(state_home),
                "TRIVIEW_NONINTERACTIVE": "1",
            }
        )

        update_result = subprocess.run(
            ["bash", str(wrapper), "--stable", "--dry-run"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        rollback_result = subprocess.run(
            ["bash", str(ROLLBACK), "--dry-run"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

        assert update_result.returncode == 2
        assert rollback_result.returncode == 2
        assert "outra operação" in (update_result.stdout + update_result.stderr)
        assert "outra operação" in (rollback_result.stdout + rollback_result.stderr)
    finally:
        if holder.poll() is None:
            os.killpg(holder.pid, signal.SIGTERM)
            holder.wait(timeout=5)
