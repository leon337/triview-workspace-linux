"""JSON configuration and serialization helpers for workspace bundles."""

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


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} precisa ser um objeto JSON.")
    return value


def layout_from_dict(value: Any) -> LayoutSpec:
    data = _mapping(value, "Layout")
    slots_value = data.get("slots")
    if not isinstance(slots_value, list):
        raise ValueError("Os slots do layout precisam ser uma lista.")
    slots = tuple(
        NormalizedRect(
            x=float(_mapping(slot, "Slot")["x"]),
            y=float(_mapping(slot, "Slot")["y"]),
            width=float(_mapping(slot, "Slot")["width"]),
            height=float(_mapping(slot, "Slot")["height"]),
            aspect_ratio=(
                float(_mapping(slot, "Slot")["aspect_ratio"])
                if _mapping(slot, "Slot").get("aspect_ratio") is not None
                else None
            ),
        )
        for slot in slots_value
    )
    if not slots:
        raise ValueError("Um layout precisa possuir ao menos um slot.")
    return LayoutSpec(id=str(data["id"]), name=str(data["name"]), slots=slots)


def panel_from_dict(value: Any) -> PanelSpec:
    data = _mapping(value, "Painel")
    metadata = data.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError("Os metadados do painel precisam ser um objeto JSON.")
    return PanelSpec(
        id=str(data["id"]),
        title=str(data["title"]),
        kind=PanelKind(str(data["kind"])),
        target=str(data["target"]),
        metadata=dict(metadata),
    )


def workspace_from_dict(value: Any) -> WorkspaceSpec:
    data = _mapping(value, "Workspace")
    panels_value = data.get("panels")
    if not isinstance(panels_value, list):
        raise ValueError("Os painéis do workspace precisam ser uma lista.")
    panels = tuple(panel_from_dict(item) for item in panels_value)
    if not panels:
        raise ValueError("Um workspace precisa possuir ao menos um painel.")
    panel_ids = {panel.id for panel in panels}
    if len(panel_ids) != len(panels):
        raise ValueError("Há painéis duplicados no workspace.")
    return WorkspaceSpec(
        id=str(data["id"]),
        name=str(data["name"]),
        layout_id=str(data["layout_id"]),
        panels=panels,
    )


def normalized_rect_to_dict(rect: NormalizedRect) -> dict[str, Any]:
    return {
        "x": rect.x,
        "y": rect.y,
        "width": rect.width,
        "height": rect.height,
        "aspect_ratio": rect.aspect_ratio,
    }


def layout_to_dict(layout: LayoutSpec) -> dict[str, Any]:
    return {
        "id": layout.id,
        "name": layout.name,
        "slots": [normalized_rect_to_dict(slot) for slot in layout.slots],
    }


def panel_to_dict(panel: PanelSpec) -> dict[str, Any]:
    return {
        "id": panel.id,
        "title": panel.title,
        "kind": panel.kind.value,
        "target": panel.target,
        "metadata": dict(panel.metadata),
    }


def workspace_to_dict(workspace: WorkspaceSpec) -> dict[str, Any]:
    return {
        "id": workspace.id,
        "name": workspace.name,
        "layout_id": workspace.layout_id,
        "panels": [panel_to_dict(panel) for panel in workspace.panels],
    }


def workspace_bundle_from_dict(
    data: Mapping[str, Any],
) -> tuple[WorkspaceSpec, LayoutSpec]:
    layout = layout_from_dict(data["layout"])
    workspace = workspace_from_dict(data["workspace"])
    if workspace.layout_id != layout.id:
        raise ValueError(
            f"Workspace espera o layout {workspace.layout_id!r}, mas recebeu {layout.id!r}."
        )
    if len(workspace.panels) > len(layout.slots):
        raise ValueError("O workspace possui mais painéis do que o layout suporta.")
    return workspace, layout


def workspace_bundle_to_dict(
    workspace: WorkspaceSpec,
    layout: LayoutSpec,
) -> dict[str, Any]:
    if workspace.layout_id != layout.id:
        raise ValueError("Workspace e layout são incompatíveis.")
    return {"layout": layout_to_dict(layout), "workspace": workspace_to_dict(workspace)}


def load_workspace_bundle(path: str | Path) -> tuple[WorkspaceSpec, LayoutSpec]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("A raiz da configuração precisa ser um objeto JSON.")
    return workspace_bundle_from_dict(data)
