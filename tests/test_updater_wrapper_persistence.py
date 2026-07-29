from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "update.sh"
ROLLBACK = ROOT / "scripts" / "stable-rollback.sh"


def test_persistent_wrapper_survives_core_overwrite_on_every_run(tmp_path: Path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    wrapper = scripts / "update.sh"
    core = scripts / "update-core.sh"
    rollback = scripts / "stable-rollback.sh"
    wrapper.write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    rollback.write_text(ROLLBACK.read_text(encoding="utf-8"), encoding="utf-8")
    core.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
updater_root="$TRIVIEW_APP_ROOT/updater"
mkdir -p "$updater_root"
cp -a "$0" "$updater_root/update.sh"
exit 0
""",
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    core.chmod(0o755)
    rollback.chmod(0o755)

    app_root = tmp_path / "app"
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "TRIVIEW_APP_ROOT": str(app_root),
            "TRIVIEW_NO_RESULT_UI": "1",
        }
    )
    expected_wrapper = wrapper.read_text(encoding="utf-8")
    expected_rollback = rollback.read_text(encoding="utf-8")

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
    assert persistent_wrapper.read_text(encoding="utf-8") == expected_wrapper
    assert persistent_core.read_text(encoding="utf-8") == core.read_text(
        encoding="utf-8"
    )
    assert persistent_rollback.read_text(encoding="utf-8") == expected_rollback

    subprocess.run(
        ["bash", str(persistent_wrapper), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert persistent_wrapper.read_text(encoding="utf-8") == expected_wrapper
    assert persistent_core.read_text(encoding="utf-8") == core.read_text(
        encoding="utf-8"
    )
    assert persistent_rollback.read_text(encoding="utf-8") == expected_rollback
