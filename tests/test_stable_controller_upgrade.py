from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def test_running_controller_installs_the_suite_from_the_new_active_release(
    tmp_path: Path,
) -> None:
    bootstrap = tmp_path / "bootstrap"
    bootstrap.mkdir()
    for name in (
        "update.sh",
        "stable-launch.sh",
        "stable-diagnose.sh",
        "stable-rollback.sh",
    ):
        target = bootstrap / name
        target.write_text((SCRIPTS / name).read_text(encoding="utf-8"), encoding="utf-8")
        target.chmod(0o755)

    core = bootstrap / "update-core.sh"
    core.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
script_dir="$(dirname "$(readlink -f "$0")")"
release="$TRIVIEW_APP_ROOT/releases/new-release"
mkdir -p "$release/scripts" "$TRIVIEW_APP_ROOT"
for name in update.sh update-core.sh stable-launch.sh stable-diagnose.sh stable-rollback.sh; do
  cp -a "$script_dir/$name" "$release/scripts/$name"
done
printf '\n# release-owned-controller\n' >> "$release/scripts/update.sh"
printf '\n# release-owned-launcher\n' >> "$release/scripts/stable-launch.sh"
temporary="$TRIVIEW_APP_ROOT/.current-upgrade"
ln -s "$release" "$temporary"
mv -Tf "$temporary" "$TRIVIEW_APP_ROOT/current"
""",
        encoding="utf-8",
    )
    core.chmod(0o755)

    home = tmp_path / "home"
    home.mkdir()
    app_root = tmp_path / "app"
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(app_root),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "TRIVIEW_NO_PAUSE": "1",
            "TRIVIEW_NO_RESULT_UI": "1",
        }
    )

    subprocess.run(
        ["bash", str(bootstrap / "update.sh"), "--stable"],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    persistent = app_root / "updater"
    assert "# release-owned-controller" in (persistent / "update.sh").read_text(
        encoding="utf-8"
    )
    assert "# release-owned-launcher" in (persistent / "stable-launch.sh").read_text(
        encoding="utf-8"
    )
    assert "# release-owned-controller" not in (bootstrap / "update.sh").read_text(
        encoding="utf-8"
    )
