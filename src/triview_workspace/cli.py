"""Main entry point: persistent GUI by default, diagnostic CLI on demand."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triview_workspace.engines import (
    BrowserPanelAdapter,
    LayoutEngine,
    PanelRegistry,
    PlaceholderPanelAdapter,
    WorkspaceEngine,
)
from triview_workspace.infrastructure import (
    WorkspaceRepository,
    load_workspace_bundle,
)

DEFAULT_WORKSPACE = Path("config/workspaces/three-mobile.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Abra ou inspecione um workspace do TriView.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help=(
            "Arquivo JSON de workspace. Quando omitido, restaura o último workspace persistido."
        ),
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=None,
        help="Caminho alternativo para o catálogo persistente de workspaces.",
    )
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Imprime o workspace calculado como JSON sem abrir a interface.",
    )
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    return parser


def resolve_workspace(
    workspace_path: Path | None,
    data_file: Path | None,
):
    """Resolve an explicit bundle or the last persisted workspace."""

    seed_workspace, seed_layout = load_workspace_bundle(DEFAULT_WORKSPACE)
    repository = WorkspaceRepository(data_file)
    catalog = repository.load_or_bootstrap(seed_workspace, seed_layout)

    if workspace_path is not None:
        workspace, layout = load_workspace_bundle(workspace_path)
        catalog = repository.save_workspace(catalog, workspace, layout, make_active=True)
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
    registry.register(BrowserPanelAdapter())
    registry.register(PlaceholderPanelAdapter())
    engine = WorkspaceEngine(LayoutEngine(), registry)
    prepared = engine.prepare(workspace, layout, width, height)

    payload = {
        "schema_version": catalog.schema_version,
        "catalog_path": str(repository.path),
        "active_workspace_id": catalog.active_workspace_id,
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
    if args.diagnostic:
        return run_diagnostic(args.workspace, args.width, args.height, args.data_file)

    from triview_workspace.gui import main as gui_main

    return gui_main(args.workspace, args.data_file)


if __name__ == "__main__":
    raise SystemExit(main())
