from __future__ import annotations

import json
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


def test_first_cli_start_repairs_an_upgrade_started_by_1_0_0a2(tmp_path: Path) -> None:
    home = tmp_path / "home"
    desktop = home / "Desktop"
    desktop.mkdir(parents=True)
    app_root = tmp_path / "app"
    updater = app_root / "updater"
    updater.mkdir(parents=True)
    (app_root / "current").symlink_to(ROOT)
    (app_root / "UPDATE_CHANNEL").write_text("stable\n", encoding="utf-8")
    (app_root / "VERSION").write_text("1.0.0a3\n", encoding="utf-8")

    # State left by the immutable 1.0.0a2 wrapper after it switches current.
    (updater / "update.sh").write_text("# old-1.0.0a2-controller\n", encoding="utf-8")
    (updater / "update-core.sh").write_text("# old-1.0.0a2-core\n", encoding="utf-8")
    (updater / "stable-rollback.sh").write_text("# old-1.0.0a2-rollback\n", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(app_root),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "TRIVIEW_SKIP_STABLE_ADOPTION": "0",
        }
    )
    command = [
        "python",
        "-c",
        "from triview_workspace.cli import adopt_stable_control_plane; "
        "adopt_stable_control_plane()",
    ]

    subprocess.run(command, env=env, check=True, capture_output=True, text=True)
    subprocess.run(command, env=env, check=True, capture_output=True, text=True)

    for name in (
        "update.sh",
        "update-core.sh",
        "stable-launch.sh",
        "stable-diagnose.sh",
        "stable-rollback.sh",
    ):
        assert (updater / name).read_bytes() == (SCRIPTS / name).read_bytes()

    commands = (
        "triview-workspace",
        "triview-workspace-update",
        "triview-workspace-diagnose",
        "triview-workspace-rollback",
    )
    for name in commands:
        assert (home / ".local" / "bin" / name).is_file()
        assert (home / ".local" / "share" / "applications" / f"{name}.desktop").is_file()

    for visible_name in (
        "TriView Workspace",
        "Atualizar TriView Workspace",
        "Diagnosticar TriView Workspace",
        "Restaurar TriView Workspace",
    ):
        assert (desktop / f"{visible_name}.desktop").is_file()

    report = json.loads(
        (
            tmp_path
            / "state"
            / "triview-workspace"
            / "stable-adoption"
            / "latest.json"
        ).read_text(encoding="utf-8")
    )
    assert report["status"] == "adopted"
    assert report["version"] == "1.0.0a3"
    assert report["controllers"] == 5
    assert report["commands"] == 4
    assert report["shortcuts"] == 4
