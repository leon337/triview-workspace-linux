"""Main entry point: GUI by default, diagnostic CLI on demand."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from triview_workspace.engines import (
    LayoutEngine,
    PanelRegistry,
    PlaceholderPanelAdapter,
    WorkspaceEngine,
)
from triview_workspace.infrastructure import load_workspace_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Open or inspect a TriView workspace.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("config/workspaces/three-mobile.json"),
        help="Path to a workspace JSON bundle.",
    )
    parser.add_argument(
        "--diagnostic",
        action="store_true",
        help="Print the calculated workspace as JSON instead of opening the GUI.",
    )
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    return parser


def run_diagnostic(workspace_path: Path, width: int, height: int) -> int:
    workspace, layout = load_workspace_bundle(workspace_path)
    registry = PanelRegistry()
    registry.register(PlaceholderPanelAdapter())
    engine = WorkspaceEngine(LayoutEngine(), registry)
    prepared = engine.prepare(workspace, layout, width, height)

    payload = {
        "workspace": workspace.name,
        "layout": layout.name,
        "viewport": {"width": width, "height": height},
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
        return run_diagnostic(args.workspace, args.width, args.height)

    from triview_workspace.gui import main as gui_main

    return gui_main(args.workspace)


if __name__ == "__main__":
    raise SystemExit(main())
