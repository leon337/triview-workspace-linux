"""Helpers for planning a safe migration from the legacy TriView installation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

LEGACY_MARKERS = ("app.py", "launcher.sh", "update.sh", "VERSION")
PRESERVE_NAMES = ("config", "data", "captures", "recordings")
PRESERVE_SUFFIXES = (".json", ".ini", ".conf", ".cfg", ".env")


@dataclass(frozen=True)
class MigrationPaths:
    legacy_app: Path
    legacy_config: Path
    app_root: Path
    backup_root: Path
    applications_dir: Path
    bin_dir: Path


def default_paths(home: Path) -> MigrationPaths:
    """Return the canonical user-scoped paths used by both generations."""

    return MigrationPaths(
        legacy_app=home / ".local" / "share" / "triview-workspace-linux",
        legacy_config=home / ".config" / "triview-workspace",
        app_root=home / ".local" / "share" / "triview-workspace",
        backup_root=home / ".local" / "share" / "triview-workspace-backups",
        applications_dir=home / ".local" / "share" / "applications",
        bin_dir=home / ".local" / "bin",
    )


def is_legacy_installation(path: Path) -> bool:
    """Return True when the directory matches the original V0.1.0 layout."""

    return path.is_dir() and all((path / marker).exists() for marker in LEGACY_MARKERS)


def discover_legacy_installation(home: Path, package_dir: Path | None = None) -> Path | None:
    """Find the installed legacy app or a legacy folder surrounding the package."""

    canonical = default_paths(home).legacy_app
    if is_legacy_installation(canonical):
        return canonical

    if package_dir is not None:
        current = package_dir.resolve()
        for candidate in (current, *current.parents[:4]):
            if is_legacy_installation(candidate):
                return candidate

    return None


def preservation_candidates(root: Path) -> tuple[Path, ...]:
    """List user-owned files and directories worth copying into the migration backup."""

    if not root.exists():
        return ()

    result: list[Path] = []
    for item in sorted(root.iterdir(), key=lambda value: value.name.lower()):
        lower_name = item.name.lower()
        if lower_name in PRESERVE_NAMES:
            result.append(item)
            continue
        if item.is_file() and (
            item.suffix.lower() in PRESERVE_SUFFIXES
            or lower_name.startswith("url")
            or lower_name.startswith("setting")
        ):
            result.append(item)
    return tuple(result)
