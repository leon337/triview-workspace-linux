from __future__ import annotations

from pathlib import Path

from triview_workspace.shortcut_reconciliation import reconcile_shortcuts


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _desktop_entry(path: Path, *, name: str, executable: Path) -> Path:
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


def test_reconciliation_installs_four_official_shortcuts_on_xdg_desktop(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    applications = home / ".local/share/applications"
    state_root = home / ".local/state/candidate"
    desktop = home / "Área de Trabalho"
    config = home / ".config/user-dirs.dirs"
    config.parent.mkdir(parents=True)
    config.write_text(
        'XDG_DESKTOP_DIR="$HOME/Área de Trabalho"\n',
        encoding="utf-8",
    )

    launchers = tuple(
        _make_executable(home / ".local/bin" / name)
        for name in (
            "triview-workspace-rc4",
            "triview-workspace-rc4-update",
            "triview-workspace-rc4-diagnose",
            "triview-workspace-rc4-rollback",
        )
    )
    sources = tuple(
        _desktop_entry(
            applications / f"{launcher.name}.desktop",
            name=launcher.name,
            executable=launcher,
        )
        for launcher in launchers
    )

    _report_path, report = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        current_launchers=launchers,
    )

    assert report["desktop_sync"]["primary_desktop_dir"] == str(desktop.resolve())
    assert report["desktop_sync"]["summary"] == {
        "created": 4,
        "updated": 0,
        "unchanged": 0,
    }
    assert len(report["desktop_sync"]["entries"]) == 4

    for source in sources:
        installed = desktop / source.name
        assert installed.is_file()
        assert installed.read_bytes() == source.read_bytes()
        assert installed.stat().st_mode & 0o111

    assert not (home / "Desktop").exists()


def test_desktop_shortcut_installation_is_idempotent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    applications = home / ".local/share/applications"
    state_root = home / ".local/state/candidate"
    desktop = home / "Desktop"
    launcher = _make_executable(home / ".local/bin/triview-workspace-rc4")
    source = _desktop_entry(
        applications / "triview-workspace-rc4.desktop",
        name="TriView Workspace",
        executable=launcher,
    )

    reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        current_launchers=(launcher,),
        desktop_dirs=(desktop,),
    )
    _report_path, second = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        current_launchers=(launcher,),
        desktop_dirs=(desktop,),
    )

    assert second["desktop_sync"]["summary"] == {
        "created": 0,
        "updated": 0,
        "unchanged": 1,
    }
    assert [path.name for path in desktop.glob("*.desktop")] == [source.name]


def test_desktop_shortcut_is_updated_when_menu_entry_changes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    applications = home / ".local/share/applications"
    state_root = home / ".local/state/candidate"
    desktop = home / "Desktop"
    launcher = _make_executable(home / ".local/bin/triview-workspace-rc4")
    source = _desktop_entry(
        applications / "triview-workspace-rc4.desktop",
        name="TriView Workspace",
        executable=launcher,
    )

    reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        current_launchers=(launcher,),
        desktop_dirs=(desktop,),
    )
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "Name=TriView Workspace",
            "Name=TriView Workspace Atualizado",
        ),
        encoding="utf-8",
    )

    _report_path, report = reconcile_shortcuts(
        home=home,
        applications_dir=applications,
        state_root=state_root,
        current_launchers=(launcher,),
        desktop_dirs=(desktop,),
    )

    assert report["desktop_sync"]["summary"] == {
        "created": 0,
        "updated": 1,
        "unchanged": 0,
    }
    assert "Atualizado" in (desktop / source.name).read_text(encoding="utf-8")
