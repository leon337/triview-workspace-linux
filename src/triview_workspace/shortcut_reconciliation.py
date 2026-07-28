"""Inventory, repair and quarantine TriView desktop shortcuts.

The reconciler is intentionally conservative: it only touches ``.desktop`` files
that clearly belong to TriView. Proven orphans are quarantined, while active
candidate entries from the applications menu are mirrored to the user's primary
XDG Desktop directory.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import shutil
import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 2
_FIELD_CODES = {
    "%f",
    "%F",
    "%u",
    "%U",
    "%d",
    "%D",
    "%n",
    "%N",
    "%i",
    "%c",
    "%k",
    "%v",
    "%m",
}


def _normalized_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _desktop_dirs_from_user_config(home: Path) -> tuple[Path, ...]:
    candidates: list[Path] = []
    config = home / ".config" / "user-dirs.dirs"
    if config.is_file():
        for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("XDG_DESKTOP_DIR="):
                continue
            value = line.split("=", 1)[1].strip().strip('"')
            value = value.replace("$HOME", str(home))
            configured = Path(os.path.expandvars(value)).expanduser()
            if _normalized_path(configured) != _normalized_path(home):
                candidates.append(configured)
            break

    # Linux Mint in pt-BR generally uses "Área de Trabalho". Keep the standard
    # English path as a portable fallback without creating duplicate desktops.
    candidates.extend((home / "Área de Trabalho", home / "Desktop"))

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        normalized = _normalized_path(candidate)
        if normalized == _normalized_path(home) or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return tuple(unique)


def _extract_exec(content: str) -> str | None:
    in_desktop_entry = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_desktop_entry = line.casefold() == "[desktop entry]"
            continue
        if in_desktop_entry and line.startswith("Exec="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None


def _command_token(exec_value: str) -> str | None:
    try:
        tokens = shlex.split(exec_value, posix=True)
    except ValueError:
        return None
    tokens = [token for token in tokens if token not in _FIELD_CODES]
    if not tokens:
        return None

    index = 0
    if Path(tokens[0]).name == "env":
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if token == "--":
                index += 1
                break
            if token.startswith("-") or ("=" in token and not token.startswith("/")):
                index += 1
                continue
            break
    return tokens[index] if index < len(tokens) else None


def _resolve_command(command: str | None, home: Path) -> tuple[Path | None, bool, str]:
    if not command:
        return None, False, "Exec ausente ou inválido"

    expanded = os.path.expandvars(os.path.expanduser(command))
    if "/" in expanded:
        path = Path(expanded)
        if not path.is_absolute():
            path = home / path
        normalized = _normalized_path(path)
        valid = normalized.is_file() and os.access(normalized, os.X_OK)
        reason = "launcher executável encontrado" if valid else "launcher informado não existe"
        return normalized, valid, reason

    located = shutil.which(expanded)
    if located is None:
        return None, False, "comando informado não foi encontrado no PATH"
    return _normalized_path(Path(located)), True, "comando encontrado no PATH"


def _is_triview_shortcut(path: Path, content: str) -> bool:
    marker = f"{path.name}\n{content}".casefold()
    return "triview" in marker


def inspect_shortcut(
    path: Path,
    *,
    scope: str,
    home: Path,
    current_launchers: Iterable[Path] = (),
) -> dict[str, Any] | None:
    """Inspect one desktop entry and return a serializable classification."""

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        if "triview" not in path.name.casefold():
            return None
        return {
            "path": str(path),
            "scope": scope,
            "status": "unreadable",
            "exec": None,
            "resolved_command": None,
            "reason": f"atalho TriView ilegível: {exc}",
        }

    if not _is_triview_shortcut(path, content):
        return None

    exec_value = _extract_exec(content)
    command = _command_token(exec_value) if exec_value is not None else None
    resolved, valid, reason = _resolve_command(command, home)
    active = {_normalized_path(item) for item in current_launchers}

    if not valid:
        status = "orphan" if exec_value is not None else "invalid"
    elif resolved in active:
        status = "candidate_active"
    else:
        status = "valid_legacy_or_stable"

    return {
        "path": str(path),
        "scope": scope,
        "status": status,
        "exec": exec_value,
        "resolved_command": str(resolved) if resolved is not None else None,
        "reason": reason,
    }


def inventory_shortcuts(
    *,
    home: Path,
    applications_dir: Path,
    desktop_dirs: Sequence[Path] | None = None,
    current_launchers: Iterable[Path] = (),
) -> list[dict[str, Any]]:
    """Return the deterministic inventory of all user-level TriView shortcuts."""

    roots: list[tuple[str, Path]] = [("applications", applications_dir)]
    roots.extend(
        ("desktop", directory)
        for directory in (desktop_dirs or _desktop_dirs_from_user_config(home))
    )

    inspected: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for scope, root in roots:
        normalized_root = _normalized_path(root)
        if not normalized_root.is_dir():
            continue
        for path in sorted(normalized_root.glob("*.desktop")):
            normalized = _normalized_path(path)
            if normalized in seen_paths:
                continue
            seen_paths.add(normalized)
            item = inspect_shortcut(
                path,
                scope=scope,
                home=home,
                current_launchers=current_launchers,
            )
            if item is not None:
                inspected.append(item)
    return inspected


def _quarantine_destination(quarantine_dir: Path, item: dict[str, Any]) -> Path:
    source = Path(str(item["path"]))
    digest = hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:10]
    return quarantine_dir / f"{item['scope']}--{digest}--{source.name}"


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def _atomic_copy_executable(source: Path, destination: Path) -> str:
    source_bytes = source.read_bytes()
    if destination.is_file() and destination.read_bytes() == source_bytes:
        destination.chmod(0o755)
        return "unchanged"

    destination.parent.mkdir(parents=True, exist_ok=True)
    existed = destination.exists() or destination.is_symlink()
    temporary = destination.with_name(f".{destination.name}.tmp-{os.getpid()}")
    temporary.write_bytes(source_bytes)
    temporary.chmod(0o755)
    temporary.replace(destination)
    return "updated" if existed else "created"


def _mark_desktop_entry_trusted(path: Path) -> bool:
    gio = shutil.which("gio")
    if gio is None:
        return False
    result = subprocess.run(
        [gio, "set", str(path), "metadata::trusted", "true"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _sync_active_shortcuts_to_desktop(
    *,
    home: Path,
    applications_dir: Path,
    desktop_dirs: Sequence[Path],
    current_launchers: Sequence[Path],
) -> dict[str, Any]:
    """Mirror active candidate shortcuts to one canonical user Desktop."""

    if not desktop_dirs:
        return {
            "primary_desktop_dir": None,
            "entries": [],
            "summary": {"created": 0, "updated": 0, "unchanged": 0},
            "status": "skipped_no_desktop_directory",
        }

    primary = _normalized_path(desktop_dirs[0])
    if primary == _normalized_path(home):
        return {
            "primary_desktop_dir": str(primary),
            "entries": [],
            "summary": {"created": 0, "updated": 0, "unchanged": 0},
            "status": "skipped_unsafe_home_directory",
        }

    primary.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    counts = {"created": 0, "updated": 0, "unchanged": 0}

    for source in sorted(_normalized_path(applications_dir).glob("*.desktop")):
        inspection = inspect_shortcut(
            source,
            scope="applications",
            home=home,
            current_launchers=current_launchers,
        )
        if inspection is None or inspection["status"] != "candidate_active":
            continue

        destination = primary / source.name
        action = _atomic_copy_executable(source, destination)
        trusted = _mark_desktop_entry_trusted(destination)
        counts[action] += 1
        entries.append(
            {
                "source": str(source),
                "destination": str(destination),
                "action": action,
                "executable": os.access(destination, os.X_OK),
                "trusted_metadata_applied": trusted,
                "resolved_command": inspection["resolved_command"],
            }
        )

    return {
        "primary_desktop_dir": str(primary),
        "entries": entries,
        "summary": counts,
        "status": "completed",
    }


def reconcile_shortcuts(
    *,
    home: Path,
    applications_dir: Path,
    state_root: Path,
    current_launchers: Sequence[Path],
    desktop_dirs: Sequence[Path] | None = None,
    now: dt.datetime | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Quarantine proven orphans, mirror active entries and write evidence."""

    timestamp = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    stamp = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    report_root = state_root / "triview-workspace" / "shortcut-reports"
    quarantine_dir = state_root / "triview-workspace" / "shortcut-quarantine" / stamp
    resolved_desktop_dirs = tuple(desktop_dirs or _desktop_dirs_from_user_config(home))

    before = inventory_shortcuts(
        home=home,
        applications_dir=applications_dir,
        desktop_dirs=resolved_desktop_dirs,
        current_launchers=current_launchers,
    )
    actions: list[dict[str, Any]] = []
    for item in before:
        if item["status"] not in {"orphan", "invalid", "unreadable"}:
            continue
        source = Path(str(item["path"]))
        if not source.exists() and not source.is_symlink():
            continue
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        destination = _quarantine_destination(quarantine_dir, item)
        shutil.move(str(source), str(destination))
        actions.append(
            {
                "action": "quarantined",
                "source": str(source),
                "destination": str(destination),
                "previous_status": item["status"],
                "reason": item["reason"],
            }
        )

    desktop_sync = _sync_active_shortcuts_to_desktop(
        home=home,
        applications_dir=applications_dir,
        desktop_dirs=resolved_desktop_dirs,
        current_launchers=current_launchers,
    )

    after = inventory_shortcuts(
        home=home,
        applications_dir=applications_dir,
        desktop_dirs=resolved_desktop_dirs,
        current_launchers=current_launchers,
    )
    payload: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "generated_at": timestamp.isoformat(),
        "home": str(home),
        "applications_dir": str(applications_dir),
        "desktop_dirs": [str(item) for item in resolved_desktop_dirs],
        "current_launchers": [str(_normalized_path(item)) for item in current_launchers],
        "before": before,
        "actions": actions,
        "desktop_sync": desktop_sync,
        "after": after,
        "summary": {
            "inspected_before": len(before),
            "quarantined": len(actions),
            "remaining_orphans": sum(
                item["status"] in {"orphan", "invalid", "unreadable"} for item in after
            ),
        },
    }

    report_path = report_root / f"{stamp}-shortcut-reconciliation.json"
    _atomic_json_write(report_path, payload)
    _atomic_json_write(report_root / "latest.json", payload)
    return report_path, payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--applications-dir", type=Path, required=True)
    parser.add_argument("--current-launcher", type=Path, action="append", default=[])
    parser.add_argument("--desktop-dir", type=Path, action="append")
    parser.add_argument("--home", type=Path, default=Path.home())
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report_path, report = reconcile_shortcuts(
        home=args.home,
        applications_dir=args.applications_dir,
        state_root=args.state_root,
        current_launchers=tuple(args.current_launcher),
        desktop_dirs=tuple(args.desktop_dir) if args.desktop_dir else None,
    )
    print(report_path)
    if report["summary"]["remaining_orphans"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
