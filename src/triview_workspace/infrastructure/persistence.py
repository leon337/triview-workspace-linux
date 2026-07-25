"""Versioned, atomic persistence for TriView workspaces."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from triview_workspace.domain import LayoutSpec, WorkspaceSpec
from triview_workspace.infrastructure.config import (
    layout_from_dict,
    layout_to_dict,
    workspace_from_dict,
    workspace_to_dict,
)

SCHEMA_VERSION = 1


class WorkspaceStorageError(RuntimeError):
    """Raised when persisted workspace data cannot be used safely."""


@dataclass(frozen=True, slots=True)
class WorkspaceCatalog:
    """Immutable snapshot of persisted layouts and workspaces."""

    schema_version: int
    active_workspace_id: str
    layouts: tuple[LayoutSpec, ...]
    workspaces: tuple[WorkspaceSpec, ...]

    def workspace_by_id(self, workspace_id: str) -> WorkspaceSpec:
        for workspace in self.workspaces:
            if workspace.id == workspace_id:
                return workspace
        raise KeyError(workspace_id)

    def layout_by_id(self, layout_id: str) -> LayoutSpec:
        for layout in self.layouts:
            if layout.id == layout_id:
                return layout
        raise KeyError(layout_id)


class WorkspaceRepository:
    """Persist a catalog with atomic replacement and recovery from invalid JSON."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else self.default_path()
        self.last_recovery_message: str | None = None

    @staticmethod
    def default_path() -> Path:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        return data_root / "triview-workspace" / "workspaces.json"

    def load_or_bootstrap(
        self,
        seed_workspace: WorkspaceSpec,
        seed_layout: LayoutSpec,
    ) -> WorkspaceCatalog:
        if not self.path.exists():
            catalog = self._catalog_from_seed(seed_workspace, seed_layout)
            self._write(catalog)
            return catalog

        try:
            return self.load()
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            backup_path = self._quarantine_invalid_file()
            self.last_recovery_message = (
                "O catálogo persistente estava inválido e foi substituído por uma cópia segura. "
                f"Arquivo preservado em: {backup_path}. Motivo: {exc}"
            )
            catalog = self._catalog_from_seed(seed_workspace, seed_layout)
            self._write(catalog)
            return catalog

    def load(self) -> WorkspaceCatalog:
        with self.path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, Mapping):
            raise WorkspaceStorageError("A raiz do catálogo precisa ser um objeto JSON.")
        return self._catalog_from_payload(payload)

    def active_bundle(self, catalog: WorkspaceCatalog) -> tuple[WorkspaceSpec, LayoutSpec]:
        workspace = catalog.workspace_by_id(catalog.active_workspace_id)
        return workspace, catalog.layout_by_id(workspace.layout_id)

    def save_workspace(
        self,
        catalog: WorkspaceCatalog,
        workspace: WorkspaceSpec,
        layout: LayoutSpec | None = None,
        *,
        make_active: bool = True,
    ) -> WorkspaceCatalog:
        layouts = {item.id: item for item in catalog.layouts}
        workspaces = {item.id: item for item in catalog.workspaces}
        if layout is not None:
            layouts[layout.id] = layout
        if workspace.layout_id not in layouts:
            raise WorkspaceStorageError(
                f"O layout {workspace.layout_id!r} do workspace não está disponível."
            )
        if len(workspace.panels) > len(layouts[workspace.layout_id].slots):
            raise WorkspaceStorageError("O workspace possui mais painéis do que o layout suporta.")
        workspaces[workspace.id] = workspace
        updated = WorkspaceCatalog(
            schema_version=SCHEMA_VERSION,
            active_workspace_id=workspace.id if make_active else catalog.active_workspace_id,
            layouts=tuple(sorted(layouts.values(), key=lambda item: item.id)),
            workspaces=tuple(sorted(workspaces.values(), key=lambda item: item.id)),
        )
        self._write(updated)
        return updated

    def set_active(self, catalog: WorkspaceCatalog, workspace_id: str) -> WorkspaceCatalog:
        catalog.workspace_by_id(workspace_id)
        updated = WorkspaceCatalog(
            schema_version=SCHEMA_VERSION,
            active_workspace_id=workspace_id,
            layouts=catalog.layouts,
            workspaces=catalog.workspaces,
        )
        self._write(updated)
        return updated

    def delete_workspace(self, catalog: WorkspaceCatalog, workspace_id: str) -> WorkspaceCatalog:
        if len(catalog.workspaces) <= 1:
            raise WorkspaceStorageError("O último workspace não pode ser excluído.")
        remaining = tuple(item for item in catalog.workspaces if item.id != workspace_id)
        if len(remaining) == len(catalog.workspaces):
            raise WorkspaceStorageError(f"Workspace não encontrado: {workspace_id}")
        active = catalog.active_workspace_id
        if active == workspace_id:
            active = remaining[0].id
        updated = WorkspaceCatalog(
            schema_version=SCHEMA_VERSION,
            active_workspace_id=active,
            layouts=catalog.layouts,
            workspaces=remaining,
        )
        self._write(updated)
        return updated

    @staticmethod
    def create_workspace_id(name: str, existing_ids: set[str]) -> str:
        base = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "workspace"
        candidate = base
        suffix = 2
        while candidate in existing_ids:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _catalog_from_payload(self, payload: Mapping[str, Any]) -> WorkspaceCatalog:
        if "schema_version" not in payload and "workspace" in payload and "layout" in payload:
            workspace = workspace_from_dict(payload["workspace"])
            layout = layout_from_dict(payload["layout"])
            catalog = self._catalog_from_seed(workspace, layout)
            self._write(catalog)
            return catalog

        version = int(payload["schema_version"])
        if version != SCHEMA_VERSION:
            raise WorkspaceStorageError(
                f"Versão de esquema não suportada: {version}. Esperada: {SCHEMA_VERSION}."
            )
        layout_items = payload.get("layouts")
        workspace_items = payload.get("workspaces")
        if not isinstance(layout_items, list) or not isinstance(workspace_items, list):
            raise WorkspaceStorageError("Layouts e workspaces precisam ser listas.")
        layouts = tuple(layout_from_dict(item) for item in layout_items)
        workspaces = tuple(workspace_from_dict(item) for item in workspace_items)
        if not layouts or not workspaces:
            raise WorkspaceStorageError("O catálogo precisa conter ao menos um layout e um workspace.")
        layout_ids = {layout.id for layout in layouts}
        if len(layout_ids) != len(layouts):
            raise WorkspaceStorageError("Há layouts duplicados no catálogo.")
        workspace_ids = {workspace.id for workspace in workspaces}
        if len(workspace_ids) != len(workspaces):
            raise WorkspaceStorageError("Há workspaces duplicados no catálogo.")
        active = str(payload["active_workspace_id"])
        if active not in workspace_ids:
            raise WorkspaceStorageError("O workspace ativo não existe no catálogo.")
        for workspace in workspaces:
            if workspace.layout_id not in layout_ids:
                raise WorkspaceStorageError(
                    f"O workspace {workspace.id!r} referencia um layout inexistente."
                )
            layout = next(item for item in layouts if item.id == workspace.layout_id)
            if len(workspace.panels) > len(layout.slots):
                raise WorkspaceStorageError(
                    f"O workspace {workspace.id!r} possui painéis demais para o layout."
                )
        return WorkspaceCatalog(version, active, layouts, workspaces)

    @staticmethod
    def _catalog_from_seed(
        workspace: WorkspaceSpec,
        layout: LayoutSpec,
    ) -> WorkspaceCatalog:
        if workspace.layout_id != layout.id:
            raise WorkspaceStorageError("Workspace e layout de origem são incompatíveis.")
        return WorkspaceCatalog(
            schema_version=SCHEMA_VERSION,
            active_workspace_id=workspace.id,
            layouts=(layout,),
            workspaces=(workspace,),
        )

    def _write(self, catalog: WorkspaceCatalog) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "active_workspace_id": catalog.active_workspace_id,
            "layouts": [layout_to_dict(item) for item in catalog.layouts],
            "workspaces": [workspace_to_dict(item) for item in catalog.workspaces],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _quarantine_invalid_file(self) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(f"{self.path.stem}.corrupt-{timestamp}{self.path.suffix}")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self.path, backup)
        return backup
