"""TriView-owned persistent references between workspaces and MCF projects.

Bindings are deliberately separate from the universal workspace catalog and from
canonical MCF state. This module never writes under ``.mcf`` and never persists
credentials, authority, mission state, evidence or runtime events.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from triview_workspace.mcf_bridge import McfRepositoryInspector

BINDING_SCHEMA_VERSION = 1
_BINDING_FIELDS = frozenset(
    {"workspace_id", "project_root", "project_id", "mission_id", "runtime_url"}
)


class McfBindingError(RuntimeError):
    """Raised when a TriView↔MCF reference cannot be trusted or persisted safely."""


@dataclass(frozen=True, slots=True)
class McfWorkspaceBinding:
    """A TriView-owned reference to canonical MCF context, never MCF authority."""

    workspace_id: str
    project_root: Path
    project_id: str
    mission_id: str | None = None
    runtime_url: str | None = None

    def __post_init__(self) -> None:
        workspace_id = self.workspace_id.strip()
        project_id = self.project_id.strip()
        if not workspace_id:
            raise McfBindingError("workspace_id não pode ser vazio")
        if not project_id:
            raise McfBindingError("project_id não pode ser vazio")
        object.__setattr__(self, "workspace_id", workspace_id)
        object.__setattr__(self, "project_id", project_id)
        object.__setattr__(self, "project_root", self.project_root.expanduser().resolve())
        object.__setattr__(self, "mission_id", _optional_text(self.mission_id))
        object.__setattr__(self, "runtime_url", _optional_text(self.runtime_url))


class McfBindingRepository:
    """Persist MCF bindings atomically in a file separate from workspaces.json."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else self.default_path()
        self.last_recovery_message: str | None = None

    @staticmethod
    def default_path() -> Path:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        return data_root / "triview-workspace" / "mcf-bindings.json"

    def load(self) -> tuple[McfWorkspaceBinding, ...]:
        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except FileNotFoundError:
            return ()
        except (OSError, json.JSONDecodeError) as exc:
            raise McfBindingError(f"Não foi possível ler o catálogo de bindings: {exc}") from exc
        return self._bindings_from_payload(payload)

    def load_or_empty(self) -> tuple[McfWorkspaceBinding, ...]:
        if not self.path.exists():
            self._write(())
            return ()
        try:
            return self.load()
        except (McfBindingError, TypeError, ValueError, KeyError) as exc:
            backup_path = self._quarantine_invalid_file()
            self.last_recovery_message = (
                "O catálogo de bindings MCF estava inválido e foi substituído por um catálogo vazio. "
                f"Arquivo preservado em: {backup_path}. Motivo: {exc}"
            )
            self._write(())
            return ()

    def get(self, workspace_id: str) -> McfWorkspaceBinding | None:
        target = workspace_id.strip()
        if not target:
            return None
        for binding in self.load():
            if binding.workspace_id == target:
                return binding
        return None

    def save(self, binding: McfWorkspaceBinding) -> McfWorkspaceBinding:
        bindings = {item.workspace_id: item for item in self.load()}
        bindings[binding.workspace_id] = binding
        self._write(tuple(sorted(bindings.values(), key=lambda item: item.workspace_id)))
        return binding

    def delete(self, workspace_id: str) -> bool:
        target = workspace_id.strip()
        bindings = self.load()
        remaining = tuple(item for item in bindings if item.workspace_id != target)
        if len(remaining) == len(bindings):
            return False
        self._write(remaining)
        return True

    @staticmethod
    def _bindings_from_payload(payload: object) -> tuple[McfWorkspaceBinding, ...]:
        if not isinstance(payload, Mapping):
            raise McfBindingError("A raiz do catálogo de bindings precisa ser um objeto JSON")
        allowed_root = {"schema_version", "bindings"}
        unknown_root = set(payload) - allowed_root
        if unknown_root:
            raise McfBindingError(
                "O catálogo de bindings contém campos não suportados: "
                + ", ".join(sorted(str(item) for item in unknown_root))
            )
        version = int(payload["schema_version"])
        if version != BINDING_SCHEMA_VERSION:
            raise McfBindingError(
                f"Versão de schema de binding não suportada: {version}. "
                f"Esperada: {BINDING_SCHEMA_VERSION}."
            )
        raw_bindings = payload["bindings"]
        if not isinstance(raw_bindings, list):
            raise McfBindingError("bindings precisa ser uma lista")

        parsed: list[McfWorkspaceBinding] = []
        seen: set[str] = set()
        for raw in raw_bindings:
            if not isinstance(raw, Mapping):
                raise McfBindingError("Cada binding precisa ser um objeto JSON")
            unknown = set(raw) - _BINDING_FIELDS
            if unknown:
                raise McfBindingError(
                    "Binding contém campos não suportados: "
                    + ", ".join(sorted(str(item) for item in unknown))
                )
            missing = {"workspace_id", "project_root", "project_id"} - set(raw)
            if missing:
                raise McfBindingError(
                    "Binding incompleto; campos obrigatórios ausentes: "
                    + ", ".join(sorted(missing))
                )
            binding = McfWorkspaceBinding(
                workspace_id=str(raw["workspace_id"]),
                project_root=Path(str(raw["project_root"])),
                project_id=str(raw["project_id"]),
                mission_id=_optional_text(raw.get("mission_id")),
                runtime_url=_optional_text(raw.get("runtime_url")),
            )
            if binding.workspace_id in seen:
                raise McfBindingError(
                    f"Há bindings duplicados para workspace_id {binding.workspace_id!r}"
                )
            seen.add(binding.workspace_id)
            parsed.append(binding)
        return tuple(sorted(parsed, key=lambda item: item.workspace_id))

    def _write(self, bindings: tuple[McfWorkspaceBinding, ...]) -> None:
        payload = {
            "schema_version": BINDING_SCHEMA_VERSION,
            "bindings": [self._binding_to_dict(item) for item in bindings],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
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

    @staticmethod
    def _binding_to_dict(binding: McfWorkspaceBinding) -> dict[str, object]:
        return {
            "workspace_id": binding.workspace_id,
            "project_root": str(binding.project_root),
            "project_id": binding.project_id,
            "mission_id": binding.mission_id,
            "runtime_url": binding.runtime_url,
        }

    def _quarantine_invalid_file(self) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(
            f"{self.path.stem}.corrupt-{timestamp}{self.path.suffix}"
        )
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self.path, backup)
        return backup


class McfWorkspaceBinder:
    """Validate canonical MCF project identity around TriView binding persistence."""

    def __init__(
        self,
        repository: McfBindingRepository | None = None,
        inspector: McfRepositoryInspector | None = None,
    ) -> None:
        self.repository = repository or McfBindingRepository()
        self.inspector = inspector or McfRepositoryInspector()

    def bind(
        self,
        workspace_id: str,
        project_root: str | Path,
        *,
        mission_id: str | None = None,
        runtime_url: str | None = None,
    ) -> McfWorkspaceBinding:
        root = Path(project_root).expanduser().resolve()
        snapshot = self.inspector.inspect(root)
        if not snapshot.is_mcf_project:
            raise McfBindingError(f"{root} não é um projeto MCF")
        if not snapshot.project_id:
            details = ", ".join(snapshot.consistency_errors) or "project_id canônico ausente"
            raise McfBindingError(
                f"Não foi possível determinar o project_id canônico em {root}: {details}"
            )
        binding = McfWorkspaceBinding(
            workspace_id=workspace_id,
            project_root=root,
            project_id=snapshot.project_id,
            mission_id=mission_id,
            runtime_url=runtime_url,
        )
        return self.repository.save(binding)

    def resolve(self, workspace_id: str) -> McfWorkspaceBinding | None:
        binding = self.repository.get(workspace_id)
        if binding is None:
            return None
        snapshot = self.inspector.inspect(binding.project_root)
        if not snapshot.is_mcf_project:
            raise McfBindingError(
                f"O binding de {workspace_id!r} aponta para um caminho que não é mais um projeto MCF"
            )
        if snapshot.project_id != binding.project_id:
            raise McfBindingError(
                "O project_id canônico divergiu do binding persistido: "
                f"esperado {binding.project_id!r}, observado {snapshot.project_id!r}"
            )
        return binding

    def unbind(self, workspace_id: str) -> bool:
        return self.repository.delete(workspace_id)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


__all__ = [
    "BINDING_SCHEMA_VERSION",
    "McfBindingError",
    "McfBindingRepository",
    "McfWorkspaceBinder",
    "McfWorkspaceBinding",
]
