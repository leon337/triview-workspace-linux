from pathlib import Path

from triview_workspace.migration import (
    default_paths,
    discover_legacy_installation,
    is_legacy_installation,
    preservation_candidates,
)


def create_legacy(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for marker in ("app.py", "launcher.sh", "update.sh", "VERSION"):
        (root / marker).write_text("test", encoding="utf-8")
    return root


def test_default_paths_match_both_installation_generations(tmp_path: Path) -> None:
    paths = default_paths(tmp_path)
    assert paths.legacy_app == tmp_path / ".local/share/triview-workspace-linux"
    assert paths.legacy_config == tmp_path / ".config/triview-workspace"
    assert paths.app_root == tmp_path / ".local/share/triview-workspace"


def test_legacy_detection_requires_all_markers(tmp_path: Path) -> None:
    candidate = tmp_path / "legacy"
    candidate.mkdir()
    (candidate / "app.py").write_text("", encoding="utf-8")
    assert not is_legacy_installation(candidate)

    create_legacy(candidate)
    assert is_legacy_installation(candidate)


def test_discovery_finds_package_nested_inside_legacy_folder(tmp_path: Path) -> None:
    legacy = create_legacy(tmp_path / "download" / "triview-workspace-linux-v0.1.0")
    package = legacy / "triview-migrador" / "app"
    package.mkdir(parents=True)
    assert discover_legacy_installation(tmp_path / "home", package) == legacy


def test_preservation_candidates_include_urls_and_config(tmp_path: Path) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "urls.json").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignore", encoding="utf-8")

    names = {item.name for item in preservation_candidates(tmp_path)}
    assert names == {"config", "data", "urls.json"}
