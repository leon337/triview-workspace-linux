"""Main entry point: persistent GUI by default, diagnostic CLI on demand."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from triview_workspace.engines import (
    ApplicationPanelAdapter,
    BrowserPanelAdapter,
    LayoutEngine,
    PanelRegistry,
    PdfPanelAdapter,
    PlaceholderPanelAdapter,
    PluginPanelAdapter,
    TerminalPanelAdapter,
    WorkspaceEngine,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle

DEFAULT_WORKSPACE = Path("config/workspaces/three-mobile.json")
STABLE_CONTROLLERS = (
    "update.sh",
    "update-core.sh",
    "stable-launch.sh",
    "stable-diagnose.sh",
    "stable-rollback.sh",
)
STABLE_COMMANDS = (
    "triview-workspace",
    "triview-workspace-update",
    "triview-workspace-diagnose",
    "triview-workspace-rollback",
)
STABLE_DESKTOP_ENTRIES = tuple(f"{name}.desktop" for name in STABLE_COMMANDS)


def _release_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _same_file_contents(left: Path, right: Path) -> bool:
    try:
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def stable_control_plane_is_current(app_root: Path, release_root: Path, home: Path) -> bool:
    updater_root = app_root / "updater"
    for name in STABLE_CONTROLLERS:
        if not _same_file_contents(release_root / "scripts" / name, updater_root / name):
            return False
    if not all((home / ".local" / "bin" / name).is_file() for name in STABLE_COMMANDS):
        return False
    applications = home / ".local" / "share" / "applications"
    return all((applications / name).is_file() for name in STABLE_DESKTOP_ENTRIES)


def adopt_stable_control_plane() -> None:
    """Adopt 1.0.0a3 controllers after an upgrade started by 1.0.0a2.

    The immutable 1.0.0a2 wrapper restores its own controller after switching the
    active release. The first CLI invocation repairs that compatibility gap before
    the GUI or diagnostic reports the new version.
    """

    if os.environ.get("TRIVIEW_SKIP_STABLE_ADOPTION") == "1":
        return

    home = Path(os.environ.get("HOME", str(Path.home()))).expanduser()
    app_root = Path(
        os.environ.get("TRIVIEW_APP_ROOT", str(home / ".local/share/triview-workspace"))
    ).expanduser()
    release_root = _release_root()
    current_link = app_root / "current"
    channel_file = app_root / "UPDATE_CHANNEL"

    try:
        current_target = current_link.resolve(strict=True)
        channel = channel_file.read_text(encoding="utf-8").strip()
    except OSError:
        return

    if current_target != release_root or channel != "stable":
        return
    if stable_control_plane_is_current(app_root, release_root, home):
        return

    adoption_script = release_root / "scripts" / "stable-adopt.sh"
    if not adoption_script.is_file():
        raise RuntimeError("controlador de adoção estável ausente na release ativa")

    environment = os.environ.copy()
    environment["HOME"] = str(home)
    environment["TRIVIEW_APP_ROOT"] = str(app_root)
    completed = subprocess.run(
        ["bash", str(adoption_script)],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "erro sem detalhes"
        raise RuntimeError(f"falha ao adotar controladores estáveis: {detail}")
    if not stable_control_plane_is_current(app_root, release_root, home):
        raise RuntimeError("adoção estável terminou sem reconciliar todos os controladores")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Abra ou inspecione um workspace do TriView.")
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--data-file", type=Path, default=None)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    return parser


def resolve_workspace(workspace_path: Path | None, data_file: Path | None):
    seed_workspace, seed_layout = load_workspace_bundle(DEFAULT_WORKSPACE)
    repository = WorkspaceRepository(data_file)
    catalog = repository.load_or_bootstrap(seed_workspace, seed_layout)
    if workspace_path is not None:
        workspace, layout = load_workspace_bundle(workspace_path)
        return repository, catalog, workspace, layout
    workspace, layout = repository.active_bundle(catalog)
    return repository, catalog, workspace, layout


def run_diagnostic(
    workspace_path: Path | None,
    width: int,
    height: int,
    data_file: Path | None = None,
) -> int:
    repository, catalog, workspace, layout = resolve_workspace(workspace_path, data_file)
    registry = PanelRegistry()
    for adapter in (
        BrowserPanelAdapter(),
        ApplicationPanelAdapter(),
        TerminalPanelAdapter(),
        PdfPanelAdapter(),
        PluginPanelAdapter(),
        PlaceholderPanelAdapter(),
    ):
        registry.register(adapter)
    prepared = WorkspaceEngine(LayoutEngine(), registry).prepare(
        workspace, layout, width, height
    )
    payload = {
        "schema_version": catalog.schema_version,
        "catalog_path": str(repository.path),
        "active_workspace_id": catalog.active_workspace_id,
        "inspected_workspace_id": workspace.id,
        "workspace": workspace.name,
        "layout": layout.name,
        "viewport": {"width": width, "height": height},
        "recovery": repository.last_recovery_message,
        "panels": [
            {
                "id": runtime.panel.id,
                "title": runtime.panel.title,
                "kind": runtime.panel.kind.value,
                "adapter": runtime.adapter_name,
                "launch_request": dict(runtime.launch_request),
                "bounds": {
                    "x": runtime.bounds.x,
                    "y": runtime.bounds.y,
                    "width": runtime.bounds.width,
                    "height": runtime.bounds.height,
                },
            }
            for runtime in prepared
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    args = build_parser().parse_args()
    adopt_stable_control_plane()
    if args.diagnostic:
        return run_diagnostic(args.workspace, args.width, args.height, args.data_file)
    from triview_workspace.gui import main as gui_main

    return gui_main(args.workspace, args.data_file)


if __name__ == "__main__":
    raise SystemExit(main())
