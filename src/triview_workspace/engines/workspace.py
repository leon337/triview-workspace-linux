"""Workspace orchestration engine."""

from __future__ import annotations

from triview_workspace.domain import LayoutSpec, RuntimePanel, WorkspaceSpec
from triview_workspace.engines.layout import LayoutEngine
from triview_workspace.engines.panels import PanelRegistry


class WorkspaceEngine:
    """Prepares all panels in a workspace for rendering or launching."""

    def __init__(self, layout_engine: LayoutEngine, panel_registry: PanelRegistry) -> None:
        self._layout_engine = layout_engine
        self._panel_registry = panel_registry

    def prepare(
        self,
        workspace: WorkspaceSpec,
        layout: LayoutSpec,
        viewport_width: int,
        viewport_height: int,
    ) -> tuple[RuntimePanel, ...]:
        if workspace.layout_id != layout.id:
            raise ValueError(
                f"Workspace expects layout {workspace.layout_id!r}, received {layout.id!r}."
            )
        if len(workspace.panels) > len(layout.slots):
            raise ValueError("Workspace has more panels than the selected layout supports.")

        bounds = self._layout_engine.calculate(layout, viewport_width, viewport_height)
        runtime_panels: list[RuntimePanel] = []

        for panel, panel_bounds in zip(workspace.panels, bounds, strict=False):
            adapter = self._panel_registry.resolve(panel.kind)
            runtime_panels.append(
                RuntimePanel(
                    panel=panel,
                    bounds=panel_bounds,
                    adapter_name=adapter.name,
                    launch_request=adapter.build_launch_request(panel),
                )
            )

        return tuple(runtime_panels)
