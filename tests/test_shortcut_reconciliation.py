from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

from triview_workspace.shortcut_reconciliation import (
    inspect_shortcut,
    reconcile_shortcuts,
)


def _write_shortcut(path: Path, *, name: str, exec_value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                "[Desktop Entry]",
                "Type=Application",
                f"Name={name}",
                f"Exec={exec_value}",
                "Terminal=false",
                "",
            )
        ),
        encoding="utf-8",
    )


def test_reconcile_quarantines_only_proven_triview_orphans(tmp_path: Path) -> None:
    home = tmp_path / "home"
    applications = home / ".local/share/applications"
    desktop = home / "Desktop"
    state_root = home / ".local/state/candidate"
    current_launcher = home / ".local/bin/triview-workspace-current"
    current_launcher.parent.mkdir(parents=True)
    current_launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    current_launcher.chmod(0o755)

    active = applications / "triview-workspace-current.desktop"
    legacy = desktop / "triview-workspace-legacy.desktop"
    orphan = desktop / "triview-workspace-dev.desktop"
    unrelated = desktop / "other-app.desktop"

    _write_shortcut(active, name="TriView atual", exec_value=str(current_launcher))
    legacy_launcher = home / ".local/bin/triview-workspace-legacy"
    legacy_launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    legacy_launcher.chmod(0o755)
    _write_shortcut(legacy, name="TriView legado", exec_value=str(legacy_launcher))
    _write_shortcut(orphan, name="TriView quebrado", exec_value=str(home / "missing"))
    _write_shortcut(unrelated, name="Outro", exec_value=str(home / "missing-other"))

    report_path, report = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        desktop_dirs=(desktop,),
        current_launchers=(current_launcher,),
        now=dt.datetime(2026, 7, 28, tzinfo=dt.timezone.utc),
    )

    assert report_path.is_file()
    assert not orphan.exists()
    assert active.exists()
    assert legacy.exists()
    assert unrelated.exists()
    assert report["summary"]["quarantined"] == 1
    assert report["summary"]["remaining_orphans"] == 0
    assert report["actions"][0]["source"] == str(orphan.resolve(strict=False))
    quarantined = Path(report["actions"][0]["destination"])
    assert quarantined.is_file()


def test_reconciliation_is_idempotent_and_updates_latest_report(tmp_path: Path) -> None:
    home = tmp_path / "home"
    applications = home / ".local/share/applications"
    desktop = home / "Desktop"
    state_root = home / ".local/state/candidate"
    launcher = home / ".local/bin/triview-workspace-current"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)
    _write_shortcut(
        applications / "triview-workspace-current.desktop",
        name="TriView atual",
        exec_value=str(launcher),
    )

    first_path, first = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        desktop_dirs=(desktop,),
        current_launchers=(launcher,),
        now=dt.datetime(2026, 7, 28, 10, 0, tzinfo=dt.timezone.utc),
    )
    second_path, second = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        desktop_dirs=(desktop,),
        current_launchers=(launcher,),
        now=dt.datetime(2026, 7, 28, 10, 1, tzinfo=dt.timezone.utc),
    )

    assert first_path != second_path
    assert first["summary"]["quarantined"] == 0
    assert second["summary"]["quarantined"] == 0
    assert second["summary"]["remaining_orphans"] == 0
    latest = state_root / "triview-workspace/shortcut-reports/latest.json"
    assert latest.is_file()
    assert json.loads(latest.read_text(encoding="utf-8"))["report_path"] == str(second_path)


def test_env_wrapped_exec_is_resolved_without_false_orphan(tmp_path: Path) -> None:
    home = tmp_path / "home"
    launcher = home / ".local/bin/triview-workspace-stable"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)
    shortcut = home / ".local/share/applications/triview-stable.desktop"
    _write_shortcut(
        shortcut,
        name="TriView estável",
        exec_value=f"env FOO=bar {launcher} --safe %U",
    )

    inspection = inspect_shortcut(
        shortcut,
        scope="applications",
        home=home,
        current_launchers=(),
    )

    assert inspection is not None
    assert inspection["status"] == "valid_legacy_or_stable"
    assert inspection["resolved_command"] == str(launcher.resolve())


def test_unreadable_non_triview_entries_are_ignored(tmp_path: Path) -> None:
    home = tmp_path / "home"
    path = home / ".local/share/applications/other.desktop"
    path.parent.mkdir(parents=True)
    path.symlink_to(home / "missing-target.desktop")

    inspection = inspect_shortcut(
        path,
        scope="applications",
        home=home,
        current_launchers=(),
    )

    assert inspection is None


def test_installer_runs_reconciliation_after_generating_current_shortcuts() -> None:
    source = Path("scripts/install-module-candidate.sh").read_text(encoding="utf-8")

    desktop_generation_position = source.index('atomic_executable "$rollback_desktop"')
    reconciliation_position = source.index("triview_workspace.shortcut_reconciliation")
    database_position = source.index('update-desktop-database "$APPLICATIONS_DIR"')

    assert desktop_generation_position < reconciliation_position < database_position
    assert source.count("--current-launcher") == 4
