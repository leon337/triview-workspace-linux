"""Versioned local library for reusable workspaces and templates."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from triview_workspace.domain import LayoutSpec, WorkspaceSpec
from triview_workspace.infrastructure.config import (
    workspace_bundle_from_dict,
    workspace_bundle_to_dict,
)

HUB_SCHEMA_VERSION = 1
HUB_DOCUMENT_KINDS = frozenset({"workspace", "template"})
_MAX_IMPORT_BYTES = 2 * 1024 * 1024
_SAFE_TOKEN = re.compile(r"[^a-z0-9-]+")


class WorkspaceHubError(ValueError):
    """Raised when a hub document or operation is unsafe or incompatible."""


@dataclass(frozen=True, slots=True)
class HubEntry:
    """Searchable metadata for one local workspace or template."""

    id: str
    name: str
    kind: str
    category: str
    favorite: bool
    path: Path
    panel_count: int
    slot_count: int


@dataclass(frozen=True, slots=True)
class HubPreview:
    """Safe structural preview without launching panel targets."""

    entry_id: str
    name: str
    kind: str
    category: str
    layout_name: str
    panel_titles: tuple[str, ...]
    panel_kinds: tuple[str, ...]
    slot_count: int


def _slug(value: str, fallback: str) -> str:
    normalized = _SAFE_TOKEN.sub("-", value.casefold()).strip("-")
    return normalized or fallback


def _unique_id(preferred: str, existing: set[str]) -> str:
    base = _slug(preferred, "workspace")
    candidate = base
    suffix = 2
    while candidate in existing:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


class WorkspaceHubRepository:
    """Persist, search, import and export versioned hub documents."""

    def __init__(self, root: str | Path | None = None) -> None:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        self.root = Path(root) if root is not None else data_root / "triview-workspace" / "hub"
        self.library = self.root / "library"
        self.metadata_path = self.root / "metadata.json"
        self.library.mkdir(parents=True, exist_ok=True)

    def add_bundle(
        self,
        workspace: WorkspaceSpec,
        layout: LayoutSpec,
        *,
        kind: str = "workspace",
        category: str = "",
        favorite: bool = False,
    ) -> HubEntry:
        normalized_kind = self._validate_kind(kind)
        entry_id = f"{normalized_kind}-{_slug(workspace.id, 'workspace')}"
        path = self.library / f"{entry_id}.json"
        if path.exists():
            raise WorkspaceHubError(f"O item {entry_id!r} já existe no Workspace Hub.")
        payload = self._payload(workspace, layout, normalized_kind, category)
        self._atomic_write(path, payload)
        self._set_metadata(entry_id, category=category, favorite=favorite)
        return self._entry_from_payload(path, payload)

    def import_file(self, source: str | Path) -> HubEntry:
        source_path = self._validate_source(source)
        payload = self._read_payload(source_path)
        workspace, _ = self._bundle(payload)
        kind = self._validate_kind(str(payload["document_kind"]))
        entry_id = f"{kind}-{_slug(workspace.id, 'workspace')}"
        destination = self.library / f"{entry_id}.json"
        if destination.exists():
            raise WorkspaceHubError(f"O item {entry_id!r} já existe no Workspace Hub.")
        normalized = dict(payload)
        normalized["hub_schema_version"] = HUB_SCHEMA_VERSION
        normalized["category"] = str(payload.get("category", "")).strip()
        self._atomic_write(destination, normalized)
        self._set_metadata(entry_id, category=normalized["category"], favorite=False)
        return self._entry_from_payload(destination, normalized)

    def export_entry(self, entry_id: str, destination: str | Path) -> Path:
        entry = self.entry(entry_id)
        destination_path = Path(destination).expanduser()
        if destination_path.exists() and destination_path.is_symlink():
            raise WorkspaceHubError("O destino de exportação não pode ser um link simbólico.")
        if destination_path.suffix.casefold() != ".json":
            destination_path = destination_path.with_suffix(".json")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._read_payload(entry.path)
        self._atomic_write(destination_path, payload)
        return destination_path

    def list_entries(self) -> tuple[HubEntry, ...]:
        entries: list[HubEntry] = []
        for path in sorted(self.library.glob("*.json")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                entries.append(self._entry_from_payload(path, self._read_payload(path)))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
        return tuple(entries)

    def search(
        self,
        query: str = "",
        *,
        category: str | None = None,
        favorites_only: bool = False,
    ) -> tuple[HubEntry, ...]:
        needle = query.strip().casefold()
        category_filter = category.strip().casefold() if category is not None else None
        matches = []
        for entry in self.list_entries():
            haystack = f"{entry.name} {entry.id} {entry.kind} {entry.category}".casefold()
            if needle and needle not in haystack:
                continue
            if category_filter is not None and entry.category.casefold() != category_filter:
                continue
            if favorites_only and not entry.favorite:
                continue
            matches.append(entry)
        return tuple(matches)

    def entry(self, entry_id: str) -> HubEntry:
        path = self.library / f"{_slug(entry_id, 'item')}.json"
        if not path.is_file() or path.is_symlink():
            raise WorkspaceHubError(f"Item não encontrado: {entry_id}")
        return self._entry_from_payload(path, self._read_payload(path))

    def load_bundle(self, entry_id: str) -> tuple[WorkspaceSpec, LayoutSpec]:
        return self._bundle(self._read_payload(self.entry(entry_id).path))

    def preview(self, entry_id: str) -> HubPreview:
        entry = self.entry(entry_id)
        workspace, layout = self.load_bundle(entry_id)
        return HubPreview(
            entry_id=entry.id,
            name=entry.name,
            kind=entry.kind,
            category=entry.category,
            layout_name=layout.name,
            panel_titles=tuple(panel.title for panel in workspace.panels),
            panel_kinds=tuple(panel.kind.value for panel in workspace.panels),
            slot_count=len(layout.slots),
        )

    def set_favorite(self, entry_id: str, favorite: bool) -> HubEntry:
        entry = self.entry(entry_id)
        self._set_metadata(entry.id, category=entry.category, favorite=favorite)
        return self.entry(entry.id)

    def set_category(self, entry_id: str, category: str) -> HubEntry:
        entry = self.entry(entry_id)
        cleaned = category.strip()
        payload = self._read_payload(entry.path)
        payload["category"] = cleaned
        self._atomic_write(entry.path, payload)
        self._set_metadata(entry.id, category=cleaned, favorite=entry.favorite)
        return self.entry(entry.id)

    def instantiate(
        self,
        entry_id: str,
        name: str,
        *,
        existing_workspace_ids: set[str],
        existing_layout_ids: set[str],
    ) -> tuple[WorkspaceSpec, LayoutSpec]:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise WorkspaceHubError("O novo workspace precisa de um nome.")
        workspace, layout = self.load_bundle(entry_id)
        workspace_id = _unique_id(cleaned_name, existing_workspace_ids)
        layout_id = _unique_id(f"{workspace_id}-layout", existing_layout_ids)
        independent_layout = replace(layout, id=layout_id, name=f"{cleaned_name} — Layout")
        independent_workspace = replace(
            workspace,
            id=workspace_id,
            name=cleaned_name,
            layout_id=layout_id,
        )
        return independent_workspace, independent_layout

    @staticmethod
    def _validate_kind(kind: str) -> str:
        normalized = kind.strip().casefold()
        if normalized not in HUB_DOCUMENT_KINDS:
            raise WorkspaceHubError(f"Tipo de documento incompatível: {kind!r}.")
        return normalized

    def _validate_source(self, source: str | Path) -> Path:
        path = Path(source).expanduser()
        if path.is_symlink():
            raise WorkspaceHubError("A importação por link simbólico não é permitida.")
        if not path.is_file():
            raise WorkspaceHubError("O arquivo de importação não existe.")
        if path.suffix.casefold() != ".json":
            raise WorkspaceHubError("O Workspace Hub aceita apenas arquivos JSON.")
        if path.stat().st_size > _MAX_IMPORT_BYTES:
            raise WorkspaceHubError("O arquivo de importação excede o limite de 2 MiB.")
        return path

    def _read_payload(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        if not isinstance(payload, dict):
            raise WorkspaceHubError("A raiz do documento precisa ser um objeto JSON.")
        if int(payload.get("hub_schema_version", 0)) != HUB_SCHEMA_VERSION:
            raise WorkspaceHubError("Versão do documento do Workspace Hub incompatível.")
        self._validate_kind(str(payload.get("document_kind", "")))
        self._bundle(payload)
        return payload

    @staticmethod
    def _bundle(payload: Mapping[str, Any]) -> tuple[WorkspaceSpec, LayoutSpec]:
        try:
            return workspace_bundle_from_dict(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkspaceHubError(f"Bundle de workspace inválido: {exc}") from exc

    @staticmethod
    def _payload(
        workspace: WorkspaceSpec,
        layout: LayoutSpec,
        kind: str,
        category: str,
    ) -> dict[str, Any]:
        payload = workspace_bundle_to_dict(workspace, layout)
        return {
            "hub_schema_version": HUB_SCHEMA_VERSION,
            "document_kind": kind,
            "category": category.strip(),
            **payload,
        }

    def _entry_from_payload(self, path: Path, payload: Mapping[str, Any]) -> HubEntry:
        workspace, layout = self._bundle(payload)
        kind = self._validate_kind(str(payload["document_kind"]))
        entry_id = path.stem
        metadata = self._metadata().get(entry_id, {})
        category = str(metadata.get("category", payload.get("category", ""))).strip()
        return HubEntry(
            id=entry_id,
            name=workspace.name,
            kind=kind,
            category=category,
            favorite=bool(metadata.get("favorite", False)),
            path=path,
            panel_count=len(workspace.panels),
            slot_count=len(layout.slots),
        )

    def _metadata(self) -> dict[str, dict[str, Any]]:
        if not self.metadata_path.is_file():
            return {}
        try:
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): dict(value)
            for key, value in payload.items()
            if isinstance(value, Mapping)
        }

    def _set_metadata(self, entry_id: str, *, category: str, favorite: bool) -> None:
        metadata = self._metadata()
        metadata[entry_id] = {"category": category.strip(), "favorite": bool(favorite)}
        self._atomic_write(self.metadata_path, metadata)

    @staticmethod
    def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
