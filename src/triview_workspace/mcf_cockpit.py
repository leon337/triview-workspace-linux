"""Read-only MCF Mission Cockpit presentation for TriView.

The cockpit consumes projections from :mod:`triview_workspace.mcf_bridge` and never
becomes a source of MCF authority. Runtime credentials are transient process input
only and are deliberately excluded from presentation models, logs and persistence.
"""

from __future__ import annotations

import os
import tkinter as tk
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from triview_workspace.mcf_binding import McfWorkspaceBinder
from triview_workspace.mcf_bridge import McfBridge, McfBridgeSnapshot, McfRuntimeClient
from triview_workspace.ui_design import (
    FONT_FAMILY,
    MONO_FONT_FAMILY,
    PALETTE,
    button_colors,
)

_ENV_PROJECT_ROOT = "TRIVIEW_MCF_PROJECT_ROOT"
_ENV_MISSION_ID = "TRIVIEW_MCF_MISSION_ID"
_ENV_RUNTIME_URL = "TRIVIEW_MCF_RUNTIME_URL"
_ENV_SESSION_TOKEN = "TRIVIEW_MCF_SESSION_TOKEN"
_GATE_EVENTS = frozenset({"GATE_REQUIRED", "GATE_APPROVED", "GATE_REJECTED"})
_MAX_TIMELINE_EVENTS = 12


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _clean_text(value: object, fallback: str = "N/A") -> str:
    if value is None:
        return fallback
    cleaned = str(value).strip()
    return cleaned or fallback


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _yes_no(value: object) -> str:
    if value is True:
        return "SIM"
    if value is False:
        return "NÃO"
    return "N/A"


def _artifact_label(status: str, detail: str | None) -> str:
    cleaned = _optional_text(detail)
    return f"{status} · {cleaned}" if cleaned else status


@dataclass(frozen=True, slots=True)
class McfCockpitEvent:
    """One compact timeline event shown without mutating runtime state."""

    event_type: str
    occurred_at: str
    agent_id: str
    phase_id: str
    summary: str


@dataclass(frozen=True, slots=True)
class McfCockpitModel:
    """Presentation-only snapshot for the four R3/R4 cockpit sections."""

    project: dict[str, str]
    mission: dict[str, str]
    authority: dict[str, str]
    continuity: dict[str, str]
    timeline: tuple[McfCockpitEvent, ...]
    mode: str = "READ_ONLY"


@dataclass(frozen=True, slots=True)
class McfCockpitContext:
    """Ephemeral read context optionally anchored by a persisted TriView binding."""

    project_root: Path
    mission_id: str | None = None
    runtime_url: str | None = None
    workspace_id: str | None = None
    binding_persisted: bool = False
    _session_token: str | None = field(default=None, repr=False, compare=False)

    @property
    def runtime_enabled(self) -> bool:
        return bool(self.mission_id and self.runtime_url and self._session_token)

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        cwd: Path | None = None,
    ) -> McfCockpitContext:
        source = os.environ if environ is None else environ
        working_directory = (cwd or Path.cwd()).expanduser().resolve()
        configured_root = _optional_text(source.get(_ENV_PROJECT_ROOT))
        project_root = (
            Path(configured_root).expanduser().resolve()
            if configured_root is not None
            else working_directory
        )
        return cls(
            project_root=project_root,
            mission_id=_optional_text(source.get(_ENV_MISSION_ID)),
            runtime_url=_optional_text(source.get(_ENV_RUNTIME_URL)),
            _session_token=_optional_text(source.get(_ENV_SESSION_TOKEN)),
        )

    @classmethod
    def for_workspace(
        cls,
        workspace_id: str,
        *,
        binder: McfWorkspaceBinder | None = None,
        environ: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> McfCockpitContext:
        """Resolve one workspace binding while keeping credentials process-only."""

        target = workspace_id.strip()
        if not target:
            raise ValueError("workspace_id não pode ser vazio")
        source = os.environ if environ is None else environ
        binding = (binder or McfWorkspaceBinder()).resolve(target)
        if binding is not None:
            return cls(
                project_root=binding.project_root,
                mission_id=binding.mission_id,
                runtime_url=binding.runtime_url,
                workspace_id=target,
                binding_persisted=True,
                _session_token=_optional_text(source.get(_ENV_SESSION_TOKEN)),
            )

        fallback = cls.from_environment(source, cwd=cwd)
        return cls(
            project_root=fallback.project_root,
            mission_id=fallback.mission_id,
            runtime_url=fallback.runtime_url,
            workspace_id=target,
            binding_persisted=False,
            _session_token=fallback._session_token,
        )


def _event_summary(event: Mapping[str, Any]) -> str:
    payload = _mapping(event.get("payload"))
    for key in ("skillId", "provider", "operation", "reason", "from", "to"):
        value = _optional_text(payload.get(key))
        if value is not None:
            return f"{key}={value}"
    return ""


def _timeline_events(runtime_timeline: Mapping[str, Any]) -> tuple[McfCockpitEvent, ...]:
    raw_events = runtime_timeline.get("events")
    if not isinstance(raw_events, list):
        return ()
    events = [item for item in raw_events if isinstance(item, Mapping)]
    events.sort(key=lambda item: _clean_text(item.get("occurredAt"), ""), reverse=True)
    return tuple(
        McfCockpitEvent(
            event_type=_clean_text(event.get("eventType")),
            occurred_at=_clean_text(event.get("occurredAt")),
            agent_id=_clean_text(event.get("agentId")),
            phase_id=_clean_text(event.get("phaseId")),
            summary=_event_summary(event),
        )
        for event in events[:_MAX_TIMELINE_EVENTS]
    )


def _latest_gate(runtime_timeline: Mapping[str, Any]) -> str:
    raw_events = runtime_timeline.get("events")
    if not isinstance(raw_events, list):
        return "N/A"
    candidates = [
        item
        for item in raw_events
        if isinstance(item, Mapping) and _clean_text(item.get("eventType"), "") in _GATE_EVENTS
    ]
    if not candidates:
        return "N/A"
    candidates.sort(key=lambda item: _clean_text(item.get("occurredAt"), ""), reverse=True)
    return _clean_text(candidates[0].get("eventType"))


def _active_standing_authorizations(contract: Mapping[str, Any]) -> int:
    raw = contract.get("standingAuthorizations")
    if not isinstance(raw, list):
        return 0
    return sum(
        1
        for item in raw
        if isinstance(item, Mapping) and _clean_text(item.get("status"), "") == "ACTIVE"
    )


def build_cockpit_model(snapshot: McfBridgeSnapshot) -> McfCockpitModel:
    """Build a stable UI projection without manufacturing missing MCF facts."""

    project_snapshot = snapshot.project
    project = {
        "root": str(project_snapshot.root),
        "mcf_project": "SIM" if project_snapshot.is_mcf_project else "NÃO",
        "project_id": _clean_text(project_snapshot.project_id),
        "methodology": _clean_text(project_snapshot.methodology_version),
        "pip": _artifact_label(project_snapshot.pip.status, project_snapshot.pip.revision_id),
        "prr": _artifact_label(project_snapshot.prr.status, project_snapshot.prr.revision_id),
        "alignment": _artifact_label(
            project_snapshot.alignment.status,
            project_snapshot.alignment.decision or project_snapshot.alignment.revision_id,
        ),
        "consistency": (
            "OK"
            if not project_snapshot.consistency_errors
            else ", ".join(project_snapshot.consistency_errors)
        ),
    }

    if snapshot.runtime is None:
        return McfCockpitModel(
            project=project,
            mission={
                "status": "NÃO CONFIGURADA",
                "mission_id": "N/A",
                "title": "N/A",
                "state": "N/A",
                "phase": "N/A",
                "agent": "N/A",
                "risk_class": "N/A",
                "entry_mode": "N/A",
            },
            authority={
                "active_standing_authorizations": "0",
                "latest_gate": "N/A",
                "blocked": "N/A",
            },
            continuity={
                "checkpoint_path": "AUSENTE",
                "checkpoint_sha": "AUSENTE",
                "resume_route": "NÃO PROJETADA NO R3",
            },
            timeline=(),
        )

    mission_payload = _mapping(snapshot.runtime.mission)
    contract = _mapping(mission_payload.get("contract"))
    observability = _mapping(snapshot.runtime.observability)
    current_phase = _mapping(observability.get("currentPhase"))
    timeline_payload = _mapping(snapshot.runtime.timeline)
    checkpoint = _mapping(contract.get("continuityCheckpointRef"))

    mission = {
        "status": "CONFIGURADA",
        "mission_id": _clean_text(mission_payload.get("id")),
        "title": _clean_text(contract.get("title")),
        "state": _clean_text(mission_payload.get("state")),
        "phase": _clean_text(
            mission_payload.get("currentPhaseId") or current_phase.get("id")
        ),
        "agent": _clean_text(
            mission_payload.get("currentAgentId") or current_phase.get("agentId")
        ),
        "risk_class": _clean_text(contract.get("riskClass")),
        "entry_mode": _clean_text(contract.get("projectEntryMode")),
    }
    authority = {
        "active_standing_authorizations": str(_active_standing_authorizations(contract)),
        "latest_gate": _latest_gate(timeline_payload),
        "blocked": _yes_no(observability.get("blocked")),
    }
    continuity = {
        "checkpoint_path": _clean_text(checkpoint.get("path"), "AUSENTE"),
        "checkpoint_sha": _clean_text(checkpoint.get("commitSha"), "AUSENTE"),
        "resume_route": "NÃO PROJETADA NO R3",
    }
    return McfCockpitModel(
        project=project,
        mission=mission,
        authority=authority,
        continuity=continuity,
        timeline=_timeline_events(timeline_payload),
    )


def load_cockpit_model(context: McfCockpitContext) -> McfCockpitModel:
    """Read repository/runtime state once and return a token-free presentation model."""

    if context.runtime_enabled:
        assert context.runtime_url is not None
        assert context.mission_id is not None
        assert context._session_token is not None
        runtime_client = McfRuntimeClient(
            context.runtime_url,
            headers={"Authorization": f"Bearer {context._session_token}"},
        )
        snapshot = McfBridge(runtime_client=runtime_client).inspect(
            context.project_root,
            mission_id=context.mission_id,
        )
    else:
        snapshot = McfBridge().inspect(context.project_root)
    return build_cockpit_model(snapshot)


def _button(
    parent: tk.Misc,
    text: str,
    command: Callable[[], object],
    *,
    variant: str = "secondary",
) -> tk.Button:
    return tk.Button(
        parent,
        text=text,
        command=command,
        relief="flat",
        bd=0,
        highlightthickness=0,
        font=(FONT_FAMILY, 9, "bold"),
        padx=12,
        pady=6,
        cursor="hand2",
        **button_colors(variant),
    )


class McfCockpitDialog:
    """Read-only Tk surface for the Mission Cockpit."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        context: McfCockpitContext | None = None,
        loader: Callable[[McfCockpitContext], McfCockpitModel] = load_cockpit_model,
    ) -> None:
        self.context = context or McfCockpitContext.from_environment()
        self.loader = loader
        self.window = tk.Toplevel(parent)
        self.window.title("MCF Mission Cockpit — somente leitura")
        self.window.configure(background=PALETTE.app)
        self.window.transient(parent)
        self.window.geometry("980x720")
        self.window.minsize(820, 560)

        header = tk.Frame(self.window, background=PALETTE.surface, height=86)
        header.pack(fill="x")
        header.pack_propagate(False)
        identity = tk.Frame(header, background=PALETTE.surface)
        identity.pack(side="left", fill="both", expand=True, padx=18, pady=12)
        tk.Label(
            identity,
            text="MCF MISSION COCKPIT",
            background=PALETTE.surface,
            foreground=PALETTE.accent_hover,
            font=(FONT_FAMILY, 15, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            identity,
            text="Projeção somente leitura · MCF permanece fonte de verdade",
            background=PALETTE.surface,
            foreground=PALETTE.text_muted,
            font=(FONT_FAMILY, 9),
            anchor="w",
        ).pack(fill="x", pady=(3, 0))

        actions = tk.Frame(header, background=PALETTE.surface)
        actions.pack(side="right", padx=18, pady=14)
        _button(actions, "Fechar", self.window.destroy, variant="ghost").pack(
            side="right", padx=(8, 0)
        )
        _button(actions, "Atualizar", self.refresh, variant="primary").pack(side="right")

        self.status_text = tk.StringVar()
        tk.Label(
            self.window,
            textvariable=self.status_text,
            background=PALETTE.surface_soft,
            foreground=PALETTE.text_muted,
            font=(MONO_FONT_FAMILY, 8),
            anchor="w",
            padx=14,
            pady=7,
        ).pack(fill="x")

        body = tk.Frame(self.window, background=PALETTE.app)
        body.pack(fill="both", expand=True, padx=14, pady=14)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=0)
        body.rowconfigure(1, weight=0)
        body.rowconfigure(2, weight=1)
        self.sections = tk.Frame(body, background=PALETTE.app)
        self.sections.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.sections.columnconfigure(0, weight=1)
        self.sections.columnconfigure(1, weight=1)

        timeline_shell = tk.Frame(
            body,
            background=PALETTE.surface,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
        )
        timeline_shell.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        tk.Label(
            timeline_shell,
            text="TIMELINE",
            background=PALETTE.surface,
            foreground=PALETTE.accent_hover,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 4))
        text_frame = tk.Frame(timeline_shell, background=PALETTE.surface)
        text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        scrollbar = tk.Scrollbar(text_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")
        self.timeline_text = tk.Text(
            text_frame,
            background=PALETTE.surface_raised,
            foreground=PALETTE.text_muted,
            insertbackground=PALETTE.text,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(MONO_FONT_FAMILY, 8),
            wrap="word",
            yscrollcommand=scrollbar.set,
            state="disabled",
        )
        self.timeline_text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.timeline_text.yview)

        self.refresh()

    def refresh(self) -> None:
        try:
            model = self.loader(self.context)
        except Exception as exc:  # noqa: BLE001
            self._render_error(exc)
            return
        self._render(model)

    def _render(self, model: McfCockpitModel) -> None:
        for child in self.sections.winfo_children():
            child.destroy()
        section_data = (
            ("PROJECT", model.project),
            ("MISSION", model.mission),
            ("AUTHORITY", model.authority),
            ("CONTINUITY", model.continuity),
        )
        for index, (title, fields) in enumerate(section_data):
            row, column = divmod(index, 2)
            self._render_section(title, fields, row=row, column=column)
        runtime_mode = "RUNTIME + REPOSITÓRIO" if self.context.runtime_enabled else "REPOSITÓRIO"
        binding_mode = "BINDING" if self.context.binding_persisted else "EFÊMERO"
        self.status_text.set(
            f"READ_ONLY · {runtime_mode} · {binding_mode} · root={self.context.project_root}"
        )
        self._render_timeline(model.timeline)

    def _render_section(
        self,
        title: str,
        fields: Mapping[str, str],
        *,
        row: int,
        column: int,
    ) -> None:
        shell = tk.Frame(
            self.sections,
            background=PALETTE.surface,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
        )
        shell.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 6, 6 if column == 0 else 0),
            pady=(0 if row == 0 else 6, 6 if row == 0 else 0),
        )
        shell.columnconfigure(1, weight=1)
        tk.Label(
            shell,
            text=title,
            background=PALETTE.surface,
            foreground=PALETTE.accent_hover,
            font=(FONT_FAMILY, 9, "bold"),
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(10, 7))
        for offset, (key, value) in enumerate(fields.items(), start=1):
            tk.Label(
                shell,
                text=key.replace("_", " ").upper(),
                background=PALETTE.surface,
                foreground=PALETTE.text_subtle,
                font=(FONT_FAMILY, 7, "bold"),
                anchor="w",
            ).grid(row=offset, column=0, sticky="nw", padx=(12, 8), pady=3)
            tk.Label(
                shell,
                text=value,
                background=PALETTE.surface,
                foreground=PALETTE.text,
                font=(MONO_FONT_FAMILY, 8),
                anchor="w",
                justify="left",
                wraplength=330,
            ).grid(row=offset, column=1, sticky="ew", padx=(0, 12), pady=3)

    def _render_timeline(self, events: tuple[McfCockpitEvent, ...]) -> None:
        self.timeline_text.configure(state="normal")
        self.timeline_text.delete("1.0", "end")
        if not events:
            self.timeline_text.insert("end", "Nenhum evento runtime projetado.\n")
        else:
            for event in events:
                summary = f" · {event.summary}" if event.summary else ""
                self.timeline_text.insert(
                    "end",
                    f"{event.occurred_at} · {event.event_type} · agent={event.agent_id} · "
                    f"phase={event.phase_id}{summary}\n",
                )
        self.timeline_text.configure(state="disabled")

    def _render_error(self, error: Exception) -> None:
        safe = str(error)
        if self.context._session_token:
            safe = safe.replace(self.context._session_token, "[REDACTED]")
        for child in self.sections.winfo_children():
            child.destroy()
        self.status_text.set(f"READ_ONLY · FALHA DE LEITURA · {safe}")
        self._render_timeline(())


def open_mcf_cockpit(
    parent: tk.Misc,
    *,
    workspace_id: str | None = None,
    binder: McfWorkspaceBinder | None = None,
    environ: Mapping[str, str] | None = None,
) -> McfCockpitDialog:
    """Open one fresh read-only cockpit for the active workspace context."""

    context = (
        McfCockpitContext.for_workspace(
            workspace_id,
            binder=binder,
            environ=environ,
        )
        if workspace_id is not None
        else McfCockpitContext.from_environment(environ)
    )
    return McfCockpitDialog(parent, context=context)


def install_mcf_cockpit(
    window: object,
    *,
    opener: Callable[..., object] = open_mcf_cockpit,
) -> None:
    """Register R4's read-only MCF action and resolve workspace identity on click."""

    register = getattr(window, "register_header_action")
    parent = getattr(window, "root")

    def open_active_workspace() -> object:
        workspace = getattr(window, "workspace", None)
        workspace_id = _optional_text(getattr(workspace, "id", None))
        return opener(parent, workspace_id=workspace_id)

    register(
        "mcf-cockpit",
        "MCF",
        open_active_workspace,
        order=40,
    )


__all__ = [
    "McfCockpitContext",
    "McfCockpitDialog",
    "McfCockpitEvent",
    "McfCockpitModel",
    "build_cockpit_model",
    "install_mcf_cockpit",
    "load_cockpit_model",
    "open_mcf_cockpit",
]
