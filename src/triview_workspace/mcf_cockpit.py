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

from triview_workspace.mcf_binding import (
    McfWorkspaceBinder,
    McfWorkspaceBinding,
)
from triview_workspace.mcf_capability_registry import (
    McfCapabilityEntryProjection,
    McfCapabilityRegistryRepositoryReader,
)
from triview_workspace.mcf_bridge import (
    McfBridge,
    McfBridgeSnapshot,
    McfRepositoryInspector,
    McfRuntimeClient,
)
from triview_workspace.mcf_continuity import (
    McfContinuityAnalyzer,
    McfContinuityDecision,
)
from triview_workspace.mcf_context_fabric import McfContextFabricRepositoryReader
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
_ENV_CONTEXT_READ_TOKEN = "TRIVIEW_MCF_CONTEXT_READ_TOKEN"
_ENV_REGISTRY_ROOT = "TRIVIEW_MCF_REGISTRY_ROOT"
_GATE_EVENTS = frozenset({"GATE_REQUIRED", "GATE_APPROVED", "GATE_REJECTED"})
_MAX_TIMELINE_EVENTS = 12
_MAX_CAPABILITY_DISPLAY_ENTRIES = 8
_MAX_CAPABILITY_SUMMARY_CHARS = 2048


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


def _registry_root(source: Mapping[str, str]) -> Path | None:
    configured = _optional_text(source.get(_ENV_REGISTRY_ROOT))
    return Path(configured).expanduser().resolve() if configured is not None else None


def _context_binder(registry_root: Path | None) -> McfWorkspaceBinder:
    return McfWorkspaceBinder(
        inspector=McfRepositoryInspector(
            context_fabric_reader=McfContextFabricRepositoryReader(
                registry_root=registry_root
            )
        )
    )


def _yes_no(value: object) -> str:
    if value is True:
        return "SIM"
    if value is False:
        return "NÃO"
    return "N/A"


def _artifact_label(status: str, detail: str | None) -> str:
    cleaned = _optional_text(detail)
    return f"{status} · {cleaned}" if cleaned else status


def _short_sha(value: str | None, fallback: str) -> str:
    return value[:12] if value else fallback


def _continuity_fields(continuity: McfContinuityDecision) -> dict[str, str]:
    return {
        "route": continuity.route,
        "reason": continuity.reason_codes[0] if continuity.reason_codes else "N/A",
        "checkpoint": _short_sha(continuity.checkpoint_sha, "AUSENTE"),
        "live": _short_sha(continuity.live_sha, "INDISPONÍVEL"),
        "drift": continuity.drift,
        "transferability": continuity.transferability or "N/A",
        "next_action": continuity.next_action or "N/A",
        "authority": continuity.authority_notice,
    }


def _context_fabric_fields(snapshot: McfBridgeSnapshot) -> dict[str, str]:
    projection = snapshot.project.context_fabric
    if projection is None:
        return {
            "status": "ABSENT",
            "project_id": "N/A",
            "registry": "AUSENTE",
            "capsule": "AUSENTE",
            "operational_freshness": "N/A",
            "identity_freshness": "N/A",
            "snapshot_status": "N/A",
            "observed_at": "N/A",
            "finding": "CONTEXT_FABRIC_NOT_INSPECTED",
        }
    return {
        "status": projection.status,
        "project_id": projection.project_id or "N/A",
        "registry": projection.registry_path or "AUSENTE",
        "capsule": projection.capsule_path or "AUSENTE",
        "operational_freshness": projection.operational_freshness or "N/A",
        "identity_freshness": projection.project_identity_freshness or "N/A",
        "snapshot_status": projection.current_status or "N/A",
        "observed_at": projection.observed_at or "N/A",
        "finding": ", ".join(projection.error_codes) or "OK",
    }


def _context_receipt_fields(snapshot: McfBridgeSnapshot) -> dict[str, str]:
    receipt = snapshot.context_receipt
    return {
        "mode": snapshot.context_mode,
        "recovery_state": receipt.recovery_state if receipt is not None else "N/A",
        "receipt_id": receipt.receipt_id if receipt is not None else "N/A",
        "evidence_only": _yes_no(receipt.evidence_only if receipt is not None else None),
        "freshness": (
            ", ".join(receipt.freshness) if receipt is not None and receipt.freshness else "N/A"
        ),
        "live_verification_required": _yes_no(
            receipt.requires_live_verification if receipt is not None else None
        ),
        "sources": str(len(receipt.sources)) if receipt is not None else "0",
        "claims": str(len(receipt.claims)) if receipt is not None else "0",
        "warning": (
            receipt.warnings[0]
            if receipt is not None and receipt.warnings
            else snapshot.context_error or "N/A"
        ),
    }


def _bounded_join(values: list[str], *, fallback: str = "N/A") -> str:
    if not values:
        return fallback
    result: list[str] = []
    length = 0
    for value in values:
        separator = 2 if result else 0
        if length + separator + len(value) > _MAX_CAPABILITY_SUMMARY_CHARS:
            result.append("…")
            break
        result.append(value)
        length += separator + len(value)
    return "; ".join(result)


def _capability_state(entry: McfCapabilityEntryProjection) -> str:
    return (
        f"{entry.capability_id} · "
        f"IMPLEMENTED={entry.implementation_state} · "
        f"CONNECTED={entry.connection_state} · "
        f"AUTHORIZED={entry.authorization_state} · "
        f"VERIFIED={entry.verification_state} · "
        f"RUNTIME={entry.runtime_state}"
    )


def _capability_gaps(entry: McfCapabilityEntryProjection) -> tuple[str, ...]:
    gaps: list[str] = []
    if entry.implementation_state != "IMPLEMENTED":
        gaps.append("NOT_IMPLEMENTED")
    if entry.connection_state != "CONNECTED":
        gaps.append("NOT_CONNECTED")
    if entry.authorization_state != "AUTHORIZED":
        gaps.append("NOT_AUTHORIZED")
    if entry.verification_state != "VERIFIED":
        gaps.append(entry.verification_state)
    if entry.runtime_state != "ACTIVE":
        gaps.append(f"RUNTIME_{entry.runtime_state}")
    return tuple(gaps)


def _capability_registry_fields(snapshot: McfBridgeSnapshot) -> dict[str, str]:
    registry = snapshot.capability_registry
    if registry is None:
        return {
            "mode": snapshot.capability_mode,
            "status": "ABSENT",
            "state_model": "IMPLEMENTED ≠ CONNECTED ≠ AUTHORIZED ≠ VERIFIED",
            "entries": "0",
            "retrieved_at": "N/A",
            "freshness": "N/A",
            "required_gates": "N/A",
            "blockers": "N/A",
            "finding": snapshot.capability_error or "CAPABILITY_REGISTRY_NOT_INSPECTED",
        }

    entries = registry.entries
    visible = entries[:_MAX_CAPABILITY_DISPLAY_ENTRIES]
    fields = {
        "mode": snapshot.capability_mode,
        "status": registry.status,
        "state_model": "IMPLEMENTED ≠ CONNECTED ≠ AUTHORIZED ≠ VERIFIED",
        "entries": str(len(entries)),
        "retrieved_at": registry.retrieved_at or "REPOSITORY_ONLY_NON_LIVE",
        "freshness": _bounded_join(sorted({entry.freshness for entry in entries})),
        "sources": str(len(registry.sources)),
    }
    for index, entry in enumerate(visible, start=1):
        fields[f"capability_{index}"] = _capability_state(entry)
    fields["entries_hidden"] = str(max(0, len(entries) - len(visible)))
    fields["required_gates"] = _bounded_join(
        [
            f"{entry.capability_id} → {entry.required_gate}"
            for entry in entries
            if entry.required_gate is not None
        ]
    )
    fields["blockers"] = _bounded_join(
        [
            f"{entry.capability_id} → {', '.join(gaps)}"
            for entry in entries
            if (gaps := _capability_gaps(entry))
        ]
    )
    fields["finding"] = (
        snapshot.capability_error
        or ", ".join(registry.error_codes)
        or "EVIDENCE_ONLY_NO_ACTIONS"
    )
    return fields


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
    """Presentation-only snapshot for MCF and Context Fabric cockpit sections."""

    project: dict[str, str]
    mission: dict[str, str]
    authority: dict[str, str]
    continuity: dict[str, str]
    context_fabric: dict[str, str]
    context_receipt: dict[str, str]
    capability_registry: dict[str, str]
    timeline: tuple[McfCockpitEvent, ...]
    mode: str = "READ_ONLY"


@dataclass(frozen=True, slots=True)
class McfCockpitContext:
    """Ephemeral read context optionally anchored by a persisted TriView binding."""

    project_root: Path
    mission_id: str | None = None
    runtime_url: str | None = None
    registry_root: Path | None = None
    workspace_id: str | None = None
    binding_persisted: bool = False
    _session_token: str | None = field(default=None, repr=False, compare=False)
    _context_read_token: str | None = field(default=None, repr=False, compare=False)

    @property
    def runtime_enabled(self) -> bool:
        return bool(self.mission_id and self.runtime_url and self._session_token)

    @property
    def context_runtime_enabled(self) -> bool:
        return bool(self.runtime_url and self._context_read_token)

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
            registry_root=_registry_root(source),
            _session_token=_optional_text(source.get(_ENV_SESSION_TOKEN)),
            _context_read_token=_optional_text(source.get(_ENV_CONTEXT_READ_TOKEN)),
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
        registry_root = _registry_root(source)
        binding = (binder or _context_binder(registry_root)).resolve(target)
        if binding is not None:
            return cls(
                project_root=binding.project_root,
                mission_id=binding.mission_id,
                runtime_url=binding.runtime_url,
                registry_root=registry_root,
                workspace_id=target,
                binding_persisted=True,
                _session_token=_optional_text(source.get(_ENV_SESSION_TOKEN)),
                _context_read_token=_optional_text(source.get(_ENV_CONTEXT_READ_TOKEN)),
            )

        fallback = cls.from_environment(source, cwd=cwd)
        return cls(
            project_root=fallback.project_root,
            mission_id=fallback.mission_id,
            runtime_url=fallback.runtime_url,
            registry_root=fallback.registry_root,
            workspace_id=target,
            binding_persisted=False,
            _session_token=fallback._session_token,
            _context_read_token=fallback._context_read_token,
        )


def binding_action_label(context: McfCockpitContext) -> str | None:
    """Return the only TriView-owned mutation exposed by the R4 cockpit."""

    if context.workspace_id is None:
        return None
    return "Desvincular workspace" if context.binding_persisted else "Vincular workspace"


def bind_workspace_context(
    context: McfCockpitContext,
    binder: McfWorkspaceBinder,
) -> McfWorkspaceBinding:
    """Persist only non-secret context references for the active workspace."""

    if context.workspace_id is None:
        raise ValueError("O Cockpit precisa de um workspace ativo para criar um binding")
    return binder.bind(
        context.workspace_id,
        context.project_root,
        mission_id=context.mission_id,
        runtime_url=context.runtime_url,
    )


def unbind_workspace_context(
    context: McfCockpitContext,
    binder: McfWorkspaceBinder,
) -> bool:
    """Remove only the TriView binding; canonical MCF state is untouched."""

    if context.workspace_id is None:
        raise ValueError("O Cockpit precisa de um workspace ativo para remover um binding")
    return binder.unbind(context.workspace_id)


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


def build_cockpit_model(
    snapshot: McfBridgeSnapshot,
    *,
    continuity: McfContinuityDecision | None = None,
) -> McfCockpitModel:
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
    context_fabric = _context_fabric_fields(snapshot)
    context_receipt = _context_receipt_fields(snapshot)
    capability_registry = _capability_registry_fields(snapshot)
    derived_continuity = _continuity_fields(continuity) if continuity is not None else None

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
            continuity=(
                derived_continuity
                if derived_continuity is not None
                else {
                    "checkpoint_path": "AUSENTE",
                    "checkpoint_sha": "AUSENTE",
                    "resume_route": "NÃO PROJETADA NO R3",
                }
            ),
            context_fabric=context_fabric,
            context_receipt=context_receipt,
            capability_registry=capability_registry,
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
    legacy_continuity = {
        "checkpoint_path": _clean_text(checkpoint.get("path"), "AUSENTE"),
        "checkpoint_sha": _clean_text(checkpoint.get("commitSha"), "AUSENTE"),
        "resume_route": "NÃO PROJETADA NO R3",
    }
    return McfCockpitModel(
        project=project,
        mission=mission,
        authority=authority,
        continuity=derived_continuity or legacy_continuity,
        context_fabric=context_fabric,
        context_receipt=context_receipt,
        capability_registry=capability_registry,
        timeline=_timeline_events(timeline_payload),
    )


def load_cockpit_model(context: McfCockpitContext) -> McfCockpitModel:
    """Read canonical evidence once and return a token-free R5 presentation model."""

    repository_inspector = McfRepositoryInspector(
        context_fabric_reader=McfContextFabricRepositoryReader(
            registry_root=context.registry_root
        )
    )
    runtime_client: McfRuntimeClient | None = None
    if context.runtime_enabled:
        assert context.runtime_url is not None
        assert context._session_token is not None
        runtime_client = McfRuntimeClient(
            context.runtime_url,
            headers={"Authorization": f"Bearer {context._session_token}"},
        )
    context_client: McfRuntimeClient | None = None
    if context.context_runtime_enabled:
        assert context.runtime_url is not None
        assert context._context_read_token is not None
        context_client = McfRuntimeClient(
            context.runtime_url,
            headers={"x-mcf-context-token": context._context_read_token},
        )
    snapshot = McfBridge(
        repository_inspector=repository_inspector,
        runtime_client=runtime_client,
        context_client=context_client,
        capability_repository_reader=McfCapabilityRegistryRepositoryReader(
            registry_root=context.registry_root
        ),
        capability_client=context_client,
    ).inspect(
        context.project_root,
        mission_id=context.mission_id if context.runtime_enabled else None,
        recover_context=context.context_runtime_enabled,
        requires_current_operational_state=False,
        list_capabilities=True,
    )
    continuity = McfContinuityAnalyzer().analyze(
        root=context.project_root,
        project=snapshot.project,
        runtime=snapshot.runtime,
        mission_id=context.mission_id,
    )
    return build_cockpit_model(snapshot, continuity=continuity)


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
    """Read-only MCF surface with TriView-only binding controls."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        context: McfCockpitContext | None = None,
        loader: Callable[[McfCockpitContext], McfCockpitModel] = load_cockpit_model,
        binder: McfWorkspaceBinder | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self.context = context or McfCockpitContext.from_environment(environ)
        self.loader = loader
        self.binder = binder or _context_binder(self.context.registry_root)
        self.environ = os.environ if environ is None else environ
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
        self.binding_button: tk.Button | None = None
        label = binding_action_label(self.context)
        if label is not None:
            self.binding_button = _button(actions, label, self._toggle_binding, variant="secondary")
            self.binding_button.pack(side="right", padx=(0, 8))

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
        body.rowconfigure(0, weight=1)

        self.body_canvas = tk.Canvas(
            body,
            background=PALETTE.app,
            bd=0,
            highlightthickness=0,
        )
        body_scrollbar = tk.Scrollbar(
            body,
            orient="vertical",
            command=self.body_canvas.yview,
        )
        self.body_canvas.configure(yscrollcommand=body_scrollbar.set)
        self.body_canvas.grid(row=0, column=0, sticky="nsew")
        body_scrollbar.grid(row=0, column=1, sticky="ns", padx=(8, 0))

        scrollable_content = tk.Frame(self.body_canvas, background=PALETTE.app)
        scrollable_content.columnconfigure(0, weight=1)
        content_window = self.body_canvas.create_window(
            (0, 0),
            window=scrollable_content,
            anchor="nw",
        )

        def update_scroll_region(_event: tk.Event[tk.Misc]) -> None:
            self.body_canvas.configure(scrollregion=self.body_canvas.bbox("all"))

        def fit_content_width(event: tk.Event[tk.Misc]) -> None:
            self.body_canvas.itemconfigure(content_window, width=event.width)

        scrollable_content.bind("<Configure>", update_scroll_region)
        self.body_canvas.bind("<Configure>", fit_content_width)
        self.window.bind("<MouseWheel>", self._scroll_body)
        self.window.bind("<Button-4>", self._scroll_body)
        self.window.bind("<Button-5>", self._scroll_body)

        self.sections = tk.Frame(scrollable_content, background=PALETTE.app)
        self.sections.grid(row=0, column=0, sticky="nsew")
        self.sections.columnconfigure(0, weight=1)
        self.sections.columnconfigure(1, weight=1)

        timeline_shell = tk.Frame(
            scrollable_content,
            background=PALETTE.surface,
            highlightbackground=PALETTE.border,
            highlightthickness=1,
        )
        timeline_shell.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
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

    def _scroll_body(self, event: tk.Event[tk.Misc]) -> str:
        if getattr(event, "num", None) == 4:
            units = -3
        elif getattr(event, "num", None) == 5:
            units = 3
        else:
            delta = int(getattr(event, "delta", 0))
            if delta == 0:
                return "break"
            units = -max(1, abs(delta) // 120) if delta > 0 else max(1, abs(delta) // 120)
        self.body_canvas.yview_scroll(units, "units")
        return "break"

    def _toggle_binding(self) -> None:
        try:
            if self.context.binding_persisted:
                unbind_workspace_context(self.context, self.binder)
            else:
                bind_workspace_context(self.context, self.binder)
            assert self.context.workspace_id is not None
            self.context = McfCockpitContext.for_workspace(
                self.context.workspace_id,
                binder=self.binder,
                environ=self.environ,
            )
        except Exception as exc:  # noqa: BLE001
            self._render_error(exc)
            return
        if self.binding_button is not None:
            self.binding_button.configure(text=binding_action_label(self.context))
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
            ("CAPABILITY REGISTRY · READ ONLY", model.capability_registry),
            ("MISSION", model.mission),
            ("AUTHORITY", model.authority),
            ("CONTINUITY", model.continuity),
            ("CONTEXT FABRIC", model.context_fabric),
            ("CONTEXT RECEIPT", model.context_receipt),
        )
        for index, (title, fields) in enumerate(section_data):
            row, column = divmod(index, 2)
            self._render_section(title, fields, row=row, column=column)
        runtime_mode = "RUNTIME + REPOSITÓRIO" if self.context.runtime_enabled else "REPOSITÓRIO"
        binding_mode = "BINDING" if self.context.binding_persisted else "EFÊMERO"
        self.status_text.set(
            f"READ_ONLY · {runtime_mode} · {model.context_receipt['mode']} · "
            f"{binding_mode} · root={self.context.project_root}"
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
        for secret in (self.context._session_token, self.context._context_read_token):
            if secret:
                safe = safe.replace(secret, "[REDACTED]")
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

    source = os.environ if environ is None else environ
    active_binder = binder or _context_binder(_registry_root(source))
    context = (
        McfCockpitContext.for_workspace(
            workspace_id,
            binder=active_binder,
            environ=environ,
        )
        if workspace_id is not None
        else McfCockpitContext.from_environment(environ)
    )
    return McfCockpitDialog(
        parent,
        context=context,
        binder=active_binder,
        environ=environ,
    )


def install_mcf_cockpit(
    window: object,
    *,
    opener: Callable[..., object] = open_mcf_cockpit,
) -> None:
    """Register R4's MCF action and resolve workspace identity on click."""

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
    "bind_workspace_context",
    "binding_action_label",
    "build_cockpit_model",
    "install_mcf_cockpit",
    "load_cockpit_model",
    "open_mcf_cockpit",
    "unbind_workspace_context",
]
