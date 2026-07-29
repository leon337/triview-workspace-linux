from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "update.sh"
STABLE_LAUNCH = ROOT / "scripts" / "stable-launch.sh"
STABLE_DIAGNOSE = ROOT / "scripts" / "stable-diagnose.sh"
ROLLBACK = ROOT / "scripts" / "stable-rollback.sh"


def test_release_owned_controller_survives_legacy_core_overwrite_on_every_run(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    wrapper = scripts / "update.sh"
    core = scripts / "update-core.sh"
    stable_launch = scripts / "stable-launch.sh"
    stable_diagnose = scripts / "stable-diagnose.sh"
    rollback = scripts / "stable-rollback.sh"
    wrapper.write_text(WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
    stable_launch.write_text(STABLE_LAUNCH.read_text(encoding="utf-8"), encoding="utf-8")
    stable_diagnose.write_text(STABLE_DIAGNOSE.read_text(encoding="utf-8"), encoding="utf-8")
    rollback.write_text(ROLLBACK.read_text(encoding="utf-8"), encoding="utf-8")
    core.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
script_dir="$(dirname "$(readlink -f "$0")")"
updater_root="$TRIVIEW_APP_ROOT/updater"
release="$TRIVIEW_APP_ROOT/releases/accepted"
mkdir -p "$updater_root" "$release/scripts"
if [[ ! -f "$release/scripts/update.sh" ]]; then
  for name in update.sh update-core.sh stable-launch.sh stable-diagnose.sh stable-rollback.sh; do
    cp -a "$script_dir/$name" "$release/scripts/$name"
  done
fi
# Simula a sobrescrita feita pelo núcleo legado no controlador persistente.
cp -a "$0" "$updater_root/update.sh"
temporary="$TRIVIEW_APP_ROOT/.current-test"
rm -f "$temporary"
ln -s "$release" "$temporary"
mv -Tf "$temporary" "$TRIVIEW_APP_ROOT/current"
exit 0
""",
        encoding="utf-8",
    )
    for path in (wrapper, core, stable_launch, stable_diagnose, rollback):
        path.chmod(0o755)

    app_root = tmp_path / "app"
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "TRIVIEW_APP_ROOT": str(app_root),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "TRIVIEW_NO_RESULT_UI": "1",
            "TRIVIEW_NO_PAUSE": "1",
        }
    )
    expected = {
        "update.sh": wrapper.read_text(encoding="utf-8"),
        "update-core.sh": core.read_text(encoding="utf-8"),
        "stable-launch.sh": stable_launch.read_text(encoding="utf-8"),
        "stable-diagnose.sh": stable_diagnose.read_text(encoding="utf-8"),
        "stable-rollback.sh": rollback.read_text(encoding="utf-8"),
    }

    subprocess.run(
        ["bash", str(wrapper), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    persistent_root = app_root / "updater"
    for name, content in expected.items():
        assert (persistent_root / name).read_text(encoding="utf-8") == content

    subprocess.run(
        ["bash", str(persistent_root / "update.sh"), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    for name, content in expected.items():
        assert (persistent_root / name).read_text(encoding="utf-8") == content
