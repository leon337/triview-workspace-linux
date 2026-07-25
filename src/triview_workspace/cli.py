"""Command-line verification entry point for the foundation."""

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
    parser = argparse.ArgumentParser(description="Prepare a TriView workspace.")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("config/workspaces/three-mobile.json"),
        help="Path to a workspace JSON bundle.",
    )
    parser.add_argument("--width", type=int, default=1366)
    parser.add_argument("--height", type=int, default=768)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace, layout = load_workspace_bundle(args.workspace)

    registry = PanelRegistry()
    registry.register(PlaceholderPanelAdapter())
    engine = WorkspaceEngine(LayoutEngine(), registry)
    prepared = engine.prepare(workspace, layout, args.width, args.height)

    payload = {
        "workspace": workspace.name,
        "layout": layout.name,
        "viewport": {"width": args.width, "height": args.height},
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


if __name__ == "__main__":
    raise SystemExit(main())
