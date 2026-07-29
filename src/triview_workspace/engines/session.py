"""Workspace session orchestration over the persistent repository."""

from __future__ import annotations

from dataclasses import replace

from triview_workspace.domain import LayoutSpec, PanelSpec, WorkspaceSpec
from triview_workspace.infrastructure import (
    WorkspaceCatalog,
    WorkspaceRepository,
    WorkspaceStorageError,
)


class WorkspaceSessionEngine:
    """Manage the active workspace without coupling persistence to Tkinter."""

    def __init__(self, repository: WorkspaceRepository, catalog: WorkspaceCatalog) -> None:
        self.repository = repository
        self.catalog = catalog

    @property
    def current_workspace(self) -> WorkspaceSpec:
        return self.catalog.workspace_by_id(self.catalog.active_workspace_id)

    @property
    def current_layout(self) -> LayoutSpec:
        return self.catalog.layout_by_id(self.current_workspace.layout_id)

    def switch(self, workspace_id: str) -> tuple[WorkspaceSpec, LayoutSpec]:
        self.catalog = self.repository.set_active(self.catalog, workspace_id)
        return self.current_workspace, self.current_layout

    def duplicate_current(self, name: str) -> tuple[WorkspaceSpec, LayoutSpec]:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("O nome do workspace não pode ficar vazio.")
        workspace_id = self.repository.create_workspace_id(
            cleaned,
            {workspace.id for workspace in self.catalog.workspaces},
        )
        workspace = replace(self.current_workspace, id=workspace_id, name=cleaned)
        self.catalog = self.repository.save_workspace(self.catalog, workspace)
        return self.current_workspace, self.current_layout

    def rename_current(self, name: str) -> tuple[WorkspaceSpec, LayoutSpec]:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("O nome do workspace não pode ficar vazio.")
        workspace = replace(self.current_workspace, name=cleaned)
        self.catalog = self.repository.save_workspace(self.catalog, workspace)
        return self.current_workspace, self.current_layout

    def update_panels(self, panels: tuple[PanelSpec, ...]) -> tuple[WorkspaceSpec, LayoutSpec]:
        if not panels:
            raise ValueError("Um workspace precisa possuir ao menos um painel.")
        if len(panels) > len(self.current_layout.slots):
            raise ValueError("O layout atual não comporta essa quantidade de painéis.")
        panel_ids = {panel.id for panel in panels}
        if len(panel_ids) != len(panels):
            raise ValueError("Os identificadores dos painéis precisam ser únicos.")
        workspace = replace(self.current_workspace, panels=panels)
        self.catalog = self.repository.save_workspace(self.catalog, workspace)
        return self.current_workspace, self.current_layout

    def save_layout(
        self,
        layout: LayoutSpec,
        *,
        select: bool = False,
    ) -> tuple[WorkspaceSpec, LayoutSpec]:
        """Persist a new layout without silently replacing an existing one."""

        if any(item.id == layout.id for item in self.catalog.layouts):
            raise WorkspaceStorageError(f"O layout {layout.id!r} já existe.")
        if select and len(self.current_workspace.panels) > len(layout.slots):
            raise ValueError("O novo layout não comporta os painéis atuais.")

        workspace = self.current_workspace
        if select:
            workspace = replace(workspace, layout_id=layout.id)

        self.catalog = self.repository.save_workspace(
            self.catalog,
            workspace,
            layout,
            make_active=True,
        )
        if select:
            return self.current_workspace, self.current_layout
        return self.current_workspace, layout

    def change_layout(self, layout_id: str) -> tuple[WorkspaceSpec, LayoutSpec]:
        layout = self.catalog.layout_by_id(layout_id)
        if len(self.current_workspace.panels) > len(layout.slots):
            raise ValueError("O layout selecionado não comporta os painéis atuais.")
        workspace = replace(self.current_workspace, layout_id=layout.id)
        self.catalog = self.repository.save_workspace(self.catalog, workspace)
        return self.current_workspace, self.current_layout

    def delete_current(self) -> tuple[WorkspaceSpec, LayoutSpec]:
        self.catalog = self.repository.delete_workspace(
            self.catalog,
            self.current_workspace.id,
        )
        return self.current_workspace, self.current_layout
