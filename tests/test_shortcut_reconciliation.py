from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from triview_workspace.shortcut_reconciliation import (
    inspect_shortcut,
    reconcile_shortcuts,
)


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _desktop(path: Path, *, name: str, executable: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                "[Desktop Entry]",
                "Type=Application",
                f"Name={name}",
                f"Exec={executable}",
                "Terminal=false",
                "",
            )
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_reconcile_quarantines_only_proven_triview_orphans(tmp_path: Path) -> None:
    home = tmp_path / "home"
    applications = home / ".local" / "share" / "applications"
    desktop = home / "Desktop"
    state_root = home / ".local" / "state" / "candidate"

    candidate_launcher = _make_executable(home / ".local/bin/triview-workspace-rc4")
    stable_launcher = _make_executable(home / ".local/bin/triview-workspace")
    candidate = _desktop(
        applications / "triview-workspace-rc4.desktop",
        name="TriView Workspace — RC4",
        executable=str(candidate_launcher),
    )
    stable = _desktop(
        applications / "triview-workspace.desktop",
        name="TriView Workspace",
        executable=str(stable_launcher),
    )
    orphan = _desktop(
        applications / "triview-workspace-dev.desktop",
        name="TriView Workspace Dev",
        executable=str(home / ".local/bin/triview-workspace-dev"),
    )
    unrelated = _desktop(
        desktop / "unrelated.desktop",
        name="Outra aplicação",
        executable=str(home / ".local/bin/missing-other-app"),
    )

    report_path, report = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        current_launchers=(candidate_launcher,),
        desktop_dirs=(desktop,),
        now=dt.datetime(2026, 7, 28, 8, 30, tzinfo=dt.timezone.utc),
    )

    assert report_path.is_file()
    assert candidate.is_file()
    assert stable.is_file()
    assert unrelated.is_file()
    assert not orphan.exists()
    assert report["summary"] == {
        "inspected_before": 3,
        "quarantined": 1,
        "remaining_orphans": 0,
    }

    before_by_name = {Path(item["path"]).name: item for item in report["before"]}
    assert before_by_name[candidate.name]["status"] == "candidate_active"
    assert before_by_name[stable.name]["status"] == "valid_legacy_or_stable"
    assert before_by_name[orphan.name]["status"] == "orphan"
    assert report["actions"][0]["source"] == str(orphan)

    quarantine = state_root / "triview-workspace" / "shortcut-quarantine"
    quarantined = list(quarantine.rglob("*triview-workspace-dev.desktop"))
    assert len(quarantined) == 1
    assert quarantined[0].read_text(encoding="utf-8").startswith("[Desktop Entry]")


def test_reconciliation_is_idempotent_and_updates_latest_report(tmp_path: Path) -> None:
    home = tmp_path / "home"
    applications = home / ".local/share/applications"
    desktop = home / "Desktop"
    state_root = home / ".local/state/candidate"
    launcher = _make_executable(home / ".local/bin/triview-workspace-rc4")
    _desktop(
        applications / "triview-workspace-dev.desktop",
        name="TriView Workspace Dev",
        executable=str(home / ".local/bin/triview-workspace-dev"),
    )

    _first_path, first = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        current_launchers=(launcher,),
        desktop_dirs=(desktop,),
        now=dt.datetime(2026, 7, 28, 8, 31, tzinfo=dt.timezone.utc),
    )
    second_path, second = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        current_launchers=(launcher,),
        desktop_dirs=(desktop,),
        now=dt.datetime(2026, 7, 28, 8, 32, tzinfo=dt.timezone.utc),
    )

    assert first["summary"]["quarantined"] == 1
    assert second["actions"] == []
    assert second["summary"]["quarantined"] == 0
    assert second["summary"]["remaining_orphans"] == 0
    latest = state_root / "triview-workspace/shortcut-reports/latest.json"
    assert json.loads(latest.read_text(encoding="utf-8")) == second
    assert json.loads(second_path.read_text(encoding="utf-8")) == second
    assert len(list((state_root / "triview-workspace/shortcut-quarantine").rglob("*.desktop"))) == 1


def test_env_wrapped_exec_is_resolved_without_false_orphan(tmp_path: Path) -> None:
    home = tmp_path / "home"
    launcher = _make_executable(home / ".local/bin/triview-workspace")
    shortcut = _desktop(
        home / ".local/share/applications/triview-workspace.desktop",
        name="TriView Workspace",
        executable=f"env TRIVIEW_MODE=stable {launcher} %U",
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
