"""Versioned operational session state without persisting secrets or process data."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from triview_workspace.domain import PanelSpec, WorkspaceSpec

RUNTIME_STATE_SCHEMA_VERSION = 1


class RuntimeStateError(RuntimeError):
    """Raised when operational session state cannot be read or written safely."""


@dataclass(frozen=True, slots=True)
class PanelSessionState:
    panel_id: str
    adapter_name: str
    configuration_hash: str
    was_open: bool
    embedded: bool
    external: bool


@dataclass(frozen=True, slots=True)
class WorkspaceRuntimeState:
    workspace_id: str
    layout_id: str
    panels: tuple[PanelSessionState, ...]


@dataclass(frozen=True, slots=True)
class RuntimeStateSnapshot:
    schema_version: int
    active_workspace_id: str | None
    clean_shutdown: bool
    saved_at: str
    workspaces: tuple[WorkspaceRuntimeState, ...]

    @staticmethod
    def empty() -> "RuntimeStateSnapshot":
        return RuntimeStateSnapshot(
            RUNTIME_STATE_SCHEMA_VERSION,
            None,
            True,
            datetime.now().astimezone().isoformat(),
            (),
        )

    def workspace(self, workspace_id: str) -> WorkspaceRuntimeState | None:
        return next(
            (item for item in self.workspaces if item.workspace_id == workspace_id),
            None,
        )


@dataclass(frozen=True, slots=True)
class RecoveryPlan:
    workspace_id: str
    panel_ids: tuple[str, ...]
    previous_clean_shutdown: bool
    saved_at: str

    @property
    def has_sessions(self) -> bool:
        return bool(self.panel_ids)


def panel_configuration_hash(panel: PanelSpec) -> str:
    """Hash kind and target so saved state never stores the raw target."""

    payload = f"{panel.kind.value}\0{panel.target}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class RuntimeStateRepository:
    """Persist runtime state atomically and quarantine malformed snapshots."""

    def __init__(self, path: str | Path | None = None) -> None:
        state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        self.path = Path(path) if path is not None else state_root / "triview-workspace" / "runtime-state.json"
        self.last_recovery_message: str | None = None

    def load_or_recover(self) -> RuntimeStateSnapshot:
        if not self.path.is_file():
            return RuntimeStateSnapshot.empty()
        try:
            return self.load()
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            quarantine = self._quarantine()
            self.last_recovery_message = (
                "O estado operacional estava inválido e foi reiniciado. "
                f"Arquivo preservado em {quarantine}. Motivo: {exc}"
            )
            snapshot = RuntimeStateSnapshot.empty()
            self.save(snapshot)
            return snapshot

    def load(self) -> RuntimeStateSnapshot:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeStateError("A raiz do estado operacional precisa ser um objeto JSON.")
        if int(payload.get("schema_version", 0)) != RUNTIME_STATE_SCHEMA_VERSION:
            raise RuntimeStateError("Versão do estado operacional incompatível.")
        workspaces_payload = payload.get("workspaces", [])
        if not isinstance(workspaces_payload, list):
            raise RuntimeStateError("A lista de workspaces do estado é inválida.")
        workspaces: list[WorkspaceRuntimeState] = []
        for item in workspaces_payload:
            if not isinstance(item, dict):
                raise RuntimeStateError("Um workspace do estado é inválido.")
            panels_payload = item.get("panels", [])
            if not isinstance(panels_payload, list):
                raise RuntimeStateError("A lista de painéis do estado é inválida.")
            panels = tuple(
                PanelSessionState(
                    panel_id=str(panel["panel_id"]),
                    adapter_name=str(panel["adapter_name"]),
                    configuration_hash=str(panel["configuration_hash"]),
                    was_open=bool(panel.get("was_open", False)),
                    embedded=bool(panel.get("embedded", False)),
                    external=bool(panel.get("external", False)),
                )
                for panel in panels_payload
            )
            workspaces.append(
                WorkspaceRuntimeState(
                    workspace_id=str(item["workspace_id"]),
                    layout_id=str(item["layout_id"]),
                    panels=panels,
                )
            )
        return RuntimeStateSnapshot(
            schema_version=RUNTIME_STATE_SCHEMA_VERSION,
            active_workspace_id=(
                str(payload["active_workspace_id"])
                if payload.get("active_workspace_id") is not None
                else None
            ),
            clean_shutdown=bool(payload.get("clean_shutdown", False)),
            saved_at=str(payload.get("saved_at", "")),
            workspaces=tuple(workspaces),
        )

    def save(self, snapshot: RuntimeStateSnapshot) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(snapshot)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".runtime-state-",
            suffix=".json",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def _quarantine(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        quarantine = self.path.with_name(f"{self.path.name}.invalid-{timestamp}")
        self.path.replace(quarantine)
        return quarantine


class SessionRecoveryEngine:
    """Build recovery plans and track open panels without storing raw targets."""

    def __init__(
        self,
        repository: RuntimeStateRepository,
        snapshot: RuntimeStateSnapshot,
    ) -> None:
        self.repository = repository
        self.snapshot = snapshot

    def recovery_plan(self, workspace: WorkspaceSpec) -> RecoveryPlan:
        state = self.snapshot.workspace(workspace.id)
        valid_panels = {panel.id: panel for panel in workspace.panels}
        panel_ids: list[str] = []
        if state is not None and state.layout_id == workspace.layout_id:
            for item in state.panels:
                panel = valid_panels.get(item.panel_id)
                if (
                    panel is not None
                    and item.was_open
                    and item.configuration_hash == panel_configuration_hash(panel)
                ):
                    panel_ids.append(item.panel_id)
        return RecoveryPlan(
            workspace.id,
            tuple(panel_ids),
            self.snapshot.clean_shutdown,
            self.snapshot.saved_at,
        )

    def begin(self, workspace: WorkspaceSpec) -> None:
        self._replace_workspace(workspace, {}, clean_shutdown=False)

    def sync(
        self,
        workspace: WorkspaceSpec,
        statuses: Mapping[str, tuple[str, bool, bool]],
        *,
        clean_shutdown: bool = False,
    ) -> None:
        self._replace_workspace(workspace, statuses, clean_shutdown=clean_shutdown)

    def finish(
        self,
        workspace: WorkspaceSpec,
        statuses: Mapping[str, tuple[str, bool, bool]],
    ) -> None:
        self._replace_workspace(workspace, statuses, clean_shutdown=True)

    def _replace_workspace(
        self,
        workspace: WorkspaceSpec,
        statuses: Mapping[str, tuple[str, bool, bool]],
        *,
        clean_shutdown: bool,
    ) -> None:
        previous = self.snapshot.workspace(workspace.id)
        previous_by_id = (
            {item.panel_id: item for item in previous.panels} if previous is not None else {}
        )
        panels: list[PanelSessionState] = []
        for panel in workspace.panels:
            adapter, embedded, external = statuses.get(
                panel.id,
                (
                    previous_by_id.get(panel.id).adapter_name
                    if panel.id in previous_by_id
                    else panel.kind.value,
                    False,
                    False,
                ),
            )
            panels.append(
                PanelSessionState(
                    panel_id=panel.id,
                    adapter_name=adapter,
                    configuration_hash=panel_configuration_hash(panel),
                    was_open=panel.id in statuses,
                    embedded=embedded,
                    external=external,
                )
            )
        workspace_state = WorkspaceRuntimeState(
            workspace.id,
            workspace.layout_id,
            tuple(panels),
        )
        workspaces = tuple(
            workspace_state if item.workspace_id == workspace.id else item
            for item in self.snapshot.workspaces
        )
        if all(item.workspace_id != workspace.id for item in workspaces):
            workspaces = (*workspaces, workspace_state)
        self.snapshot = RuntimeStateSnapshot(
            RUNTIME_STATE_SCHEMA_VERSION,
            workspace.id,
            clean_shutdown,
            datetime.now().astimezone().isoformat(),
            workspaces,
        )
        self.repository.save(self.snapshot)
