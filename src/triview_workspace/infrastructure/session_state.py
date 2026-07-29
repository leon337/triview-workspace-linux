"""Versioned and privacy-aware operational session persistence."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from triview_workspace.domain import PanelKind, PanelSpec, WorkspaceSpec
from triview_workspace.infrastructure.persistence import WorkspaceCatalog

SESSION_SCHEMA_VERSION = 1
_SUPPORTED_VIEW_MODES = frozenset({"all", "dual", "focus"})
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SENSITIVE_KEY = re.compile(
    r"(?:password|passwd|secret|token|cookie|authorization|auth|credential|history|clipboard|profile)",
    re.IGNORECASE,
)
_ALLOWED_STATE_KEYS: dict[PanelKind, frozenset[str]] = {
    PanelKind.BROWSER: frozenset({"url"}),
    PanelKind.APPLICATION: frozenset({"working_directory"}),
    PanelKind.TERMINAL: frozenset({"working_directory"}),
    PanelKind.PDF: frozenset({"path", "page", "zoom"}),
    PanelKind.CUSTOM: frozenset(),
}


@dataclass(frozen=True, slots=True)
class PanelSessionState:
    """Safe operational state for one panel."""

    panel_id: str
    kind: PanelKind
    state: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class WorkspaceSessionSnapshot:
    """One versioned workspace checkpoint restored independently of its catalog."""

    schema_version: int
    workspace_id: str
    layout_id: str
    focused_panel_id: str | None
    view_mode: str
    panels: tuple[PanelSessionState, ...]
    saved_at: str


@dataclass(frozen=True, slots=True)
class SessionLoadResult:
    """A non-fatal load result with diagnostics suitable for logs and UI."""

    snapshot: WorkspaceSessionSnapshot | None
    diagnostics: tuple[str, ...] = ()


def _safe_workspace_id(workspace_id: str) -> str:
    value = str(workspace_id)
    if not _SAFE_ID.fullmatch(value):
        raise ValueError(f"Identificador de workspace inseguro: {value!r}.")
    return value


def _safe_string(value: Any, *, maximum: int = 4096) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > maximum or "\x00" in cleaned:
        return None
    return cleaned


def _sanitize_url(value: Any) -> str | None:
    url = _safe_string(value, maximum=8192)
    if url is None:
        return None
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https", "file", "about"}:
        return None
    if parsed.username or parsed.password:
        host = parsed.hostname or ""
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        parsed = parsed._replace(netloc=host)
    safe_query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not _SENSITIVE_KEY.search(key)
    ]
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(safe_query, doseq=True),
            "",
        )
    )


def _sanitize_path(value: Any) -> str | None:
    path = _safe_string(value)
    if path is None:
        return None
    candidate = Path(path).expanduser()
    if ".." in candidate.parts:
        return None
    return str(candidate)


def sanitize_panel_state(kind: PanelKind, state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Apply a strict per-adapter allowlist and remove secret-bearing fields."""

    if not isinstance(state, Mapping):
        return {}
    allowed = _ALLOWED_STATE_KEYS[kind]
    safe: dict[str, Any] = {}
    for raw_key, raw_value in state.items():
        key = str(raw_key)
        if key not in allowed or _SENSITIVE_KEY.search(key):
            continue
        if key == "url":
            value = _sanitize_url(raw_value)
        elif key in {"working_directory", "path"}:
            value = _sanitize_path(raw_value)
        elif key == "page":
            value = raw_value if isinstance(raw_value, int) and raw_value >= 1 else None
        elif key == "zoom":
            value = (
                float(raw_value)
                if isinstance(raw_value, (int, float)) and 0.1 <= float(raw_value) <= 10.0
                else None
            )
        else:
            value = None
        if value is not None:
            safe[key] = value
    return safe


def _default_panel_state(panel: PanelSpec) -> dict[str, Any]:
    if panel.kind is PanelKind.BROWSER:
        return {"url": panel.target}
    if panel.kind in {PanelKind.APPLICATION, PanelKind.TERMINAL}:
        return {"working_directory": panel.metadata.get("working_directory")}
    if panel.kind is PanelKind.PDF:
        return {
            "path": panel.target,
            "page": panel.metadata.get("page"),
            "zoom": panel.metadata.get("zoom"),
        }
    return {}


def snapshot_from_workspace(
    workspace: WorkspaceSpec,
    *,
    focused_panel_id: str | None = None,
    view_mode: str = "all",
    runtime_states: Mapping[str, Mapping[str, Any]] | None = None,
) -> WorkspaceSessionSnapshot:
    """Build a checkpoint without serializing histories, credentials or profiles."""

    panel_ids = {panel.id for panel in workspace.panels}
    focused = focused_panel_id if focused_panel_id in panel_ids else None
    mode = view_mode if view_mode in _SUPPORTED_VIEW_MODES else "all"
    supplied = runtime_states if isinstance(runtime_states, Mapping) else {}
    panels: list[PanelSessionState] = []
    for panel in workspace.panels:
        merged = _default_panel_state(panel)
        runtime = supplied.get(panel.id)
        if isinstance(runtime, Mapping):
            merged.update(runtime)
        panels.append(
            PanelSessionState(
                panel_id=panel.id,
                kind=panel.kind,
                state=sanitize_panel_state(panel.kind, merged),
            )
        )
    return WorkspaceSessionSnapshot(
        schema_version=SESSION_SCHEMA_VERSION,
        workspace_id=_safe_workspace_id(workspace.id),
        layout_id=workspace.layout_id,
        focused_panel_id=focused,
        view_mode=mode,
        panels=tuple(panels),
        saved_at=datetime.now(UTC).isoformat(),
    )


def apply_snapshot_to_workspace(
    workspace: WorkspaceSpec,
    snapshot: WorkspaceSessionSnapshot,
) -> tuple[WorkspaceSpec, tuple[str, ...]]:
    """Restore supported panel fields while isolating malformed individual entries."""

    diagnostics: list[str] = []
    if snapshot.workspace_id != workspace.id:
        return workspace, (
            f"Sessão {snapshot.workspace_id!r} ignorada para workspace {workspace.id!r}.",
        )
    if snapshot.layout_id != workspace.layout_id:
        diagnostics.append(
            f"Layout da sessão {snapshot.layout_id!r} difere do layout atual {workspace.layout_id!r}; "
            "o layout atual foi preservado."
        )
    state_by_id = {item.panel_id: item for item in snapshot.panels}
    restored: list[PanelSpec] = []
    for panel in workspace.panels:
        item = state_by_id.get(panel.id)
        if item is None:
            restored.append(panel)
            continue
        if item.kind is not panel.kind:
            diagnostics.append(
                f"Estado do painel {panel.id!r} ignorado porque o tipo mudou de "
                f"{item.kind.value!r} para {panel.kind.value!r}."
            )
            restored.append(panel)
            continue
        safe = sanitize_panel_state(panel.kind, item.state)
        try:
            target = panel.target
            metadata = dict(panel.metadata)
            if panel.kind is PanelKind.BROWSER and "url" in safe:
                target = str(safe["url"])
            elif panel.kind in {PanelKind.APPLICATION, PanelKind.TERMINAL}:
                if "working_directory" in safe:
                    metadata["working_directory"] = safe["working_directory"]
            elif panel.kind is PanelKind.PDF:
                if "path" in safe:
                    target = str(safe["path"])
                for key in ("page", "zoom"):
                    if key in safe:
                        metadata[key] = safe[key]
            restored.append(replace(panel, target=target, metadata=metadata))
        except (TypeError, ValueError) as exc:
            diagnostics.append(f"Estado parcial do painel {panel.id!r} ignorado: {exc}")
            restored.append(panel)
    return replace(workspace, panels=tuple(restored)), tuple(diagnostics)


class SessionStateRepository:
    """Persist per-workspace session snapshots atomically with private permissions."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            state_root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            root = state_root / "triview-workspace" / "sessions"
        self.root = Path(root)

    def path_for(self, workspace_id: str) -> Path:
        return self.root / f"{_safe_workspace_id(workspace_id)}.json"

    def save(self, snapshot: WorkspaceSessionSnapshot) -> Path:
        path = self.path_for(snapshot.workspace_id)
        payload = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "workspace_id": snapshot.workspace_id,
            "layout_id": snapshot.layout_id,
            "focused_panel_id": snapshot.focused_panel_id,
            "view_mode": snapshot.view_mode,
            "saved_at": snapshot.saved_at,
            "panels": [
                {
                    "panel_id": item.panel_id,
                    "kind": item.kind.value,
                    "state": sanitize_panel_state(item.kind, item.state),
                }
                for item in snapshot.panels
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
            path.chmod(0o600)
        finally:
            temporary.unlink(missing_ok=True)
        return path

    def load(self, workspace_id: str) -> SessionLoadResult:
        path = self.path_for(workspace_id)
        if not path.exists():
            return SessionLoadResult(None)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping):
                raise ValueError("a raiz precisa ser um objeto JSON")
            version = int(payload.get("schema_version", -1))
            if version != SESSION_SCHEMA_VERSION:
                return SessionLoadResult(
                    None,
                    (
                        f"Sessão de {workspace_id!r} usa esquema {version}; "
                        f"esperado {SESSION_SCHEMA_VERSION}. Estado ignorado.",
                    ),
                )
            if str(payload.get("workspace_id")) != workspace_id:
                return SessionLoadResult(
                    None,
                    (f"Arquivo de sessão não pertence ao workspace {workspace_id!r}.",),
                )
            diagnostics: list[str] = []
            panels: list[PanelSessionState] = []
            raw_panels = payload.get("panels", [])
            if not isinstance(raw_panels, list):
                diagnostics.append("Lista de painéis da sessão inválida; estados individuais ignorados.")
                raw_panels = []
            for index, raw in enumerate(raw_panels):
                try:
                    if not isinstance(raw, Mapping):
                        raise ValueError("entrada não é um objeto")
                    panel_id = _safe_workspace_id(str(raw["panel_id"]))
                    kind = PanelKind(str(raw["kind"]))
                    state = sanitize_panel_state(kind, raw.get("state"))
                    panels.append(PanelSessionState(panel_id, kind, state))
                except (KeyError, TypeError, ValueError) as exc:
                    diagnostics.append(f"Painel de sessão #{index + 1} ignorado: {exc}")
            view_mode = str(payload.get("view_mode", "all"))
            if view_mode not in _SUPPORTED_VIEW_MODES:
                diagnostics.append(f"Modo de visualização {view_mode!r} inválido; usando 'all'.")
                view_mode = "all"
            focused = payload.get("focused_panel_id")
            focused_panel_id = str(focused) if isinstance(focused, str) else None
            snapshot = WorkspaceSessionSnapshot(
                schema_version=SESSION_SCHEMA_VERSION,
                workspace_id=workspace_id,
                layout_id=str(payload.get("layout_id", "")),
                focused_panel_id=focused_panel_id,
                view_mode=view_mode,
                panels=tuple(panels),
                saved_at=str(payload.get("saved_at", "")),
            )
            return SessionLoadResult(snapshot, tuple(diagnostics))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            backup = self._quarantine(path)
            return SessionLoadResult(
                None,
                (
                    f"Sessão inválida de {workspace_id!r} foi isolada em {backup}: {exc}",
                ),
            )

    @staticmethod
    def _quarantine(path: Path) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(f"{path.stem}.invalid-{timestamp}{path.suffix}")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(path, backup)
        return backup


def restore_catalog_sessions(
    catalog: WorkspaceCatalog,
    repository: SessionStateRepository,
) -> tuple[WorkspaceCatalog, tuple[str, ...]]:
    """Restore every workspace independently so one bad snapshot never blocks startup."""

    diagnostics: list[str] = []
    restored: list[WorkspaceSpec] = []
    for workspace in catalog.workspaces:
        result = repository.load(workspace.id)
        diagnostics.extend(result.diagnostics)
        if result.snapshot is None:
            restored.append(workspace)
            continue
        updated, item_diagnostics = apply_snapshot_to_workspace(workspace, result.snapshot)
        diagnostics.extend(item_diagnostics)
        restored.append(updated)
    return replace(catalog, workspaces=tuple(restored)), tuple(diagnostics)
