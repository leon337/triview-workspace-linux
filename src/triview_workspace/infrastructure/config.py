"""JSON configuration loader for workspace bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from triview_workspace.domain import (
    LayoutSpec,
    NormalizedRect,
    PanelKind,
    PanelSpec,
    WorkspaceSpec,
)


def workspace_bundle_from_dict(
    data: Mapping[str, Any],
) -> tuple[WorkspaceSpec, LayoutSpec]:
    layout_data = data["layout"]
    workspace_data = data["workspace"]

    slots = tuple(
        NormalizedRect(
            x=float(slot["x"]),
            y=float(slot["y"]),
            width=float(slot["width"]),
            height=float(slot["height"]),
            aspect_ratio=(
                float(slot["aspect_ratio"])
                if slot.get("aspect_ratio") is not None
                else None
            ),
        )
        for slot in layout_data["slots"]
    )

    panels = tuple(
        PanelSpec(
            id=str(panel["id"]),
            title=str(panel["title"]),
            kind=PanelKind(str(panel["kind"])),
            target=str(panel["target"]),
            metadata=dict(panel.get("metadata", {})),
        )
        for panel in workspace_data["panels"]
    )

    layout = LayoutSpec(
        id=str(layout_data["id"]),
        name=str(layout_data["name"]),
        slots=slots,
    )
    workspace = WorkspaceSpec(
        id=str(workspace_data["id"]),
        name=str(workspace_data["name"]),
        layout_id=str(workspace_data["layout_id"]),
        panels=panels,
    )
    return workspace, layout


def load_workspace_bundle(path: str | Path) -> tuple[WorkspaceSpec, LayoutSpec]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Workspace configuration root must be a JSON object.")
    return workspace_bundle_from_dict(data)
