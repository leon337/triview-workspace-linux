from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from triview_workspace.mcf_binding import McfWorkspaceBinding
from triview_workspace.mcf_bridge import (
    McfArtifactProjection,
    McfBridgeSnapshot,
    McfRepositorySnapshot,
    McfRuntimeProjection,
)
from triview_workspace.mcf_capability_registry import (
    McfCapabilityEntryProjection,
    McfCapabilityEvidenceProjection,
    McfCapabilityRegistryProjection,
)
from triview_workspace.mcf_cockpit import (
    McfCockpitContext,
    McfCockpitDialog,
    build_cockpit_model,
    install_mcf_cockpit,
)


def _project_snapshot(root: Path) -> McfRepositorySnapshot:
    return McfRepositorySnapshot(
        root=root,
        is_mcf_project=True,
        project_id="triview",
        methodology_version="v1.1.0",
        pip=McfArtifactProjection(
            status="VALID",
            artifact_type="PROJECT_INTENT_PACKAGE",
            path=str(root / ".mcf/intent/pip-r1.json"),
            project_id="triview",
            revision_id="r1",
            schema_version="1.0",
            methodology_version="v1.1.0",
            methodology_ref="5d79f488407c77f7b9f21ecfefb41ddfb3a52aef",
        ),
        prr=McfArtifactProjection(
            status="VALID",
            artifact_type="PROJECT_REALITY_REPORT",
            path=str(root / ".mcf/reality/prr-r1.json"),
            project_id="triview",
            revision_id="r1",
            schema_version="1.0",
            methodology_version="v1.1.0",
            methodology_ref="5d79f488407c77f7b9f21ecfefb41ddfb3a52aef",
        ),
        alignment=McfArtifactProjection(
            status="VALID",
            artifact_type="INTENT_ALIGNMENT_RECEIPT",
            path=str(root / ".mcf/receipts/intent-alignment-a1.json"),
            project_id="triview",
            revision_id="a1",
            schema_version="1.0",
            decision="PASS",
        ),
    )


def _runtime_projection() -> McfRuntimeProjection:
    mission = {
        "id": "mission-1",
        "state": "EXECUTING",
        "currentPhaseId": "phase-2",
        "currentAgentId": "Sofia",
        "version": 7,
        "contract": {
            "title": "Reconcile TriView",
            "riskClass": "B",
            "projectId": "triview",
            "projectEntryMode": "ADOPT_EXISTING_PROJECT",
            "standingAuthorizations": [
                {"authorizationId": "auth-1", "status": "ACTIVE"},
                {"authorizationId": "auth-2", "status": "REVOKED"},
            ],
            "continuityCheckpointRef": {
                "artifactType": "MISSION_CHECKPOINT",
                "path": ".mcf/checkpoints/c1.json",
                "commitSha": "abc1234",
            },
        },
    }
    return McfRuntimeProjection(
        mission=mission,
        timeline={
            "mission": mission,
            "events": [
                {
                    "id": "event-gate",
                    "eventType": "GATE_REQUIRED",
                    "occurredAt": "2026-08-17T06:00:00Z",
                    "agentId": "Leo",
                    "phaseId": "phase-2",
                    "payload": {},
                },
                {
                    "id": "event-phase",
                    "eventType": "PHASE_STARTED",
                    "occurredAt": "2026-08-17T06:01:00Z",
                    "agentId": "Sofia",
                    "phaseId": "phase-2",
                    "payload": {"skillId": "MCF-DESIGN-ARCHITECTURE"},
                },
            ],
        },
        observability={
            "mission": mission,
            "currentPhase": {
                "id": "phase-2",
                "skillId": "MCF-DESIGN-ARCHITECTURE",
                "agentId": "Sofia",
                "state": "EXECUTING",
                "cycle": 1,
            },
            "latestEvent": None,
            "blocked": False,
            "blockContext": None,
        },
    )


def _capability_entry(
    capability_id: str,
    *,
    connection: str,
    authorization: str,
    runtime: str,
    verification: str,
    gate: str,
) -> McfCapabilityEntryProjection:
    return McfCapabilityEntryProjection(
        capability_id=capability_id,
        provider_project_id="multiagent-collaboration-framework",
        consumer_project_ids=("triview",),
        mode="READ_ONLY",
        protocol="MCF_CONTEXT_HTTP_V1",
        allowed_operations=("context.read",),
        prohibited_operations=("context.write",),
        environments=("lab",),
        resources=("context/capabilities",),
        authorization_state=authorization,
        required_gate=gate,
        expiration=None,
        implementation_state="IMPLEMENTED",
        connection_state=connection,
        runtime_state=runtime,
        verification_state=verification,
        last_verified_at="2026-08-23T06:30:22Z",
        evidence=(
            McfCapabilityEvidenceProjection(
                source_ref="context/capabilities/fixture.yaml",
                source_revision="fixture-revision",
            ),
        ),
        freshness="LIVE_REQUIRED",
    )


def test_cockpit_model_projects_repository_only_state(tmp_path: Path) -> None:
    model = build_cockpit_model(
        McfBridgeSnapshot(project=_project_snapshot(tmp_path), runtime=None)
    )

    assert model.project["project_id"] == "triview"
    assert model.project["methodology"] == "v1.1.0"
    assert model.project["pip"] == "VALID · r1"
    assert model.project["prr"] == "VALID · r1"
    assert model.project["alignment"] == "VALID · PASS"
    assert model.mission["status"] == "NÃO CONFIGURADA"
    assert model.authority["active_standing_authorizations"] == "0"
    assert model.authority["latest_gate"] == "N/A"
    assert model.continuity["checkpoint_path"] == "AUSENTE"
    assert model.continuity["resume_route"] == "NÃO PROJETADA NO R3"
    assert model.capability_registry["mode"] == "REPOSITORY_ONLY"
    assert model.capability_registry["status"] == "ABSENT"
    assert model.timeline == ()


def test_cockpit_keeps_capability_states_gates_and_blockers_visibly_distinct(
    tmp_path: Path,
) -> None:
    disconnected = _capability_entry(
        "cloud.workspace.g2a.read",
        connection="DISCONNECTED",
        authorization="NOT_AUTHORIZED",
        runtime="UNKNOWN",
        verification="HISTORICALLY_VERIFIED",
        gate="DEDICATED_FORCED_COMMAND_SSH_READ_TRANSPORT",
    )
    active = _capability_entry(
        "mcf.context.recovery.read",
        connection="CONNECTED",
        authorization="AUTHORIZED",
        runtime="ACTIVE",
        verification="VERIFIED",
        gate="DEDICATED_CONTEXT_READ_TOKEN",
    )
    model = build_cockpit_model(
        McfBridgeSnapshot(
            project=_project_snapshot(tmp_path),
            runtime=None,
            capability_registry=McfCapabilityRegistryProjection(
                status="VALID",
                project_id="triview",
                retrieved_at="2026-08-23T06:50:00Z",
                entries=(disconnected, active),
                sources=disconnected.evidence + active.evidence,
                source="MCF_CAPABILITY_REGISTRY_GET_READ_ONLY",
            ),
            capability_mode="MCF_RUNTIME_GET",
        )
    )

    capabilities = model.capability_registry
    assert capabilities["state_model"] == ("IMPLEMENTED ≠ CONNECTED ≠ AUTHORIZED ≠ VERIFIED")
    assert capabilities["capability_1"] == (
        "cloud.workspace.g2a.read · IMPLEMENTED=IMPLEMENTED · "
        "CONNECTED=DISCONNECTED · AUTHORIZED=NOT_AUTHORIZED · "
        "VERIFIED=HISTORICALLY_VERIFIED · RUNTIME=UNKNOWN"
    )
    assert "cloud.workspace.g2a.read → NOT_CONNECTED, NOT_AUTHORIZED" in capabilities["blockers"]
    assert "HISTORICALLY_VERIFIED" in capabilities["blockers"]
    assert "mcf.context.recovery.read" not in capabilities["blockers"]
    assert "DEDICATED_FORCED_COMMAND_SSH_READ_TRANSPORT" in capabilities["required_gates"]
    assert capabilities["finding"] == "EVIDENCE_ONLY_NO_ACTIONS"
    assert model.mode == "READ_ONLY"


def test_cockpit_model_projects_mission_authority_continuity_and_timeline(
    tmp_path: Path,
) -> None:
    model = build_cockpit_model(
        McfBridgeSnapshot(
            project=_project_snapshot(tmp_path),
            runtime=_runtime_projection(),
        )
    )

    assert model.mission["mission_id"] == "mission-1"
    assert model.mission["title"] == "Reconcile TriView"
    assert model.mission["state"] == "EXECUTING"
    assert model.mission["phase"] == "phase-2"
    assert model.mission["agent"] == "Sofia"
    assert model.mission["risk_class"] == "B"
    assert model.mission["entry_mode"] == "ADOPT_EXISTING_PROJECT"
    assert model.authority["active_standing_authorizations"] == "1"
    assert model.authority["latest_gate"] == "GATE_REQUIRED"
    assert model.authority["blocked"] == "NÃO"
    assert model.continuity["checkpoint_path"] == ".mcf/checkpoints/c1.json"
    assert model.continuity["checkpoint_sha"] == "abc1234"
    assert model.continuity["resume_route"] == "NÃO PROJETADA NO R3"
    assert [event.event_type for event in model.timeline] == [
        "PHASE_STARTED",
        "GATE_REQUIRED",
    ]
    assert model.timeline[0].agent_id == "Sofia"


def test_cockpit_context_reads_runtime_configuration_without_exposing_token(
    tmp_path: Path,
) -> None:
    context = McfCockpitContext.from_environment(
        {
            "TRIVIEW_MCF_PROJECT_ROOT": str(tmp_path),
            "TRIVIEW_MCF_MISSION_ID": "mission-1",
            "TRIVIEW_MCF_RUNTIME_URL": "https://mcf.example.test/",
            "TRIVIEW_MCF_SESSION_TOKEN": "secret-token",
            "TRIVIEW_MCF_CONTEXT_READ_TOKEN": "context-read-token",
            "TRIVIEW_MCF_MISSION_CONTROL_REPOSITORY": "leon337/multiagent-collaboration-framework",
            "TRIVIEW_MCF_MISSION_CONTROL_TOKEN": "mission-control-token",
            "TRIVIEW_MCF_REGISTRY_ROOT": str(tmp_path / "mcf-registry"),
        },
        cwd=tmp_path.parent,
    )

    assert context.project_root == tmp_path.resolve()
    assert context.mission_id == "mission-1"
    assert context.runtime_url == "https://mcf.example.test/"
    assert context.runtime_enabled is True
    assert context.context_runtime_enabled is True
    assert context.mission_control_enabled is True
    assert context.mission_control_repository == ("leon337/multiagent-collaboration-framework")
    assert context.registry_root == (tmp_path / "mcf-registry").resolve()
    assert "secret-token" not in repr(context)
    assert "context-read-token" not in repr(context)
    assert "mission-control-token" not in repr(context)


def test_cockpit_context_disables_runtime_when_configuration_is_incomplete(
    tmp_path: Path,
) -> None:
    context = McfCockpitContext.from_environment(
        {
            "TRIVIEW_MCF_PROJECT_ROOT": str(tmp_path),
            "TRIVIEW_MCF_MISSION_ID": "mission-1",
            "TRIVIEW_MCF_RUNTIME_URL": "https://mcf.example.test",
        },
        cwd=tmp_path.parent,
    )

    assert context.project_root == tmp_path.resolve()
    assert context.runtime_enabled is False
    assert context.context_runtime_enabled is False
    assert context.mission_control_enabled is False


def test_cockpit_context_keeps_mission_and_context_credentials_independent(
    tmp_path: Path,
) -> None:
    mission_only = McfCockpitContext.from_environment(
        {
            "TRIVIEW_MCF_PROJECT_ROOT": str(tmp_path),
            "TRIVIEW_MCF_MISSION_ID": "mission-1",
            "TRIVIEW_MCF_RUNTIME_URL": "https://mcf.example.test",
            "TRIVIEW_MCF_SESSION_TOKEN": "mission-only",
        }
    )
    context_only = McfCockpitContext.from_environment(
        {
            "TRIVIEW_MCF_PROJECT_ROOT": str(tmp_path),
            "TRIVIEW_MCF_RUNTIME_URL": "https://mcf.example.test",
            "TRIVIEW_MCF_CONTEXT_READ_TOKEN": "context-only",
        }
    )

    assert mission_only.runtime_enabled is True
    assert mission_only.context_runtime_enabled is False
    assert context_only.runtime_enabled is False
    assert context_only.context_runtime_enabled is True
    assert "mission-only" not in repr(mission_only)
    assert "context-only" not in repr(context_only)


def test_cockpit_context_defaults_project_root_to_current_directory(tmp_path: Path) -> None:
    context = McfCockpitContext.from_environment({}, cwd=tmp_path)

    assert context.project_root == tmp_path.resolve()
    assert context.mission_id is None
    assert context.runtime_url is None
    assert context.runtime_enabled is False
    assert context.context_runtime_enabled is False
    assert context.registry_root is None


def test_workspace_binding_overrides_non_secret_environment_but_token_remains_ephemeral(
    tmp_path: Path,
) -> None:
    bound_root = tmp_path / "bound-project"
    fallback_root = tmp_path / "fallback-project"
    binding = McfWorkspaceBinding(
        workspace_id="workspace-a",
        project_root=bound_root,
        project_id="project-a",
        mission_id="bound-mission",
        runtime_url="https://bound.example.test/",
    )

    class FakeBinder:
        def resolve(self, workspace_id: str) -> McfWorkspaceBinding | None:
            assert workspace_id == "workspace-a"
            return binding

    context = McfCockpitContext.for_workspace(
        "workspace-a",
        binder=FakeBinder(),  # type: ignore[arg-type]
        environ={
            "TRIVIEW_MCF_PROJECT_ROOT": str(fallback_root),
            "TRIVIEW_MCF_MISSION_ID": "fallback-mission",
            "TRIVIEW_MCF_RUNTIME_URL": "https://fallback.example.test/",
            "TRIVIEW_MCF_SESSION_TOKEN": "ephemeral-token",
            "TRIVIEW_MCF_CONTEXT_READ_TOKEN": "ephemeral-context-token",
        },
        cwd=tmp_path,
    )

    assert context.workspace_id == "workspace-a"
    assert context.binding_persisted is True
    assert context.project_root == bound_root.resolve()
    assert context.mission_id == "bound-mission"
    assert context.runtime_url == "https://bound.example.test/"
    assert context.runtime_enabled is True
    assert context.context_runtime_enabled is True
    assert "ephemeral-token" not in repr(context)
    assert "ephemeral-context-token" not in repr(context)


def test_unbound_workspace_preserves_r3_environment_fallback(tmp_path: Path) -> None:
    class FakeBinder:
        def resolve(self, workspace_id: str) -> None:
            assert workspace_id == "workspace-a"
            return None

    context = McfCockpitContext.for_workspace(
        "workspace-a",
        binder=FakeBinder(),  # type: ignore[arg-type]
        environ={
            "TRIVIEW_MCF_PROJECT_ROOT": str(tmp_path / "fallback"),
            "TRIVIEW_MCF_MISSION_ID": "fallback-mission",
            "TRIVIEW_MCF_RUNTIME_URL": "https://fallback.example.test/",
        },
        cwd=tmp_path,
    )

    assert context.workspace_id == "workspace-a"
    assert context.binding_persisted is False
    assert context.project_root == (tmp_path / "fallback").resolve()
    assert context.mission_id == "fallback-mission"
    assert context.runtime_url == "https://fallback.example.test/"
    assert context.runtime_enabled is False


def test_installer_resolves_active_workspace_at_click_time() -> None:
    registered: list[tuple[str, str, object, int]] = []
    opened: list[tuple[object, str | None]] = []

    @dataclass
    class Workspace:
        id: str

    class FakeWindow:
        root = object()
        workspace = Workspace("workspace-a")

        def register_header_action(
            self,
            action_id: str,
            label: str,
            command: object,
            *,
            order: int = 100,
        ) -> None:
            registered.append((action_id, label, command, order))

    def opener(parent: object, *, workspace_id: str | None = None) -> None:
        opened.append((parent, workspace_id))

    window = FakeWindow()
    install_mcf_cockpit(window, opener=opener)

    assert len(registered) == 1
    action_id, label, command, order = registered[0]
    assert action_id == "mcf-cockpit"
    assert label == "MCF"
    assert order == 40
    assert callable(command)

    command()  # type: ignore[operator]
    window.workspace = Workspace("workspace-b")
    command()  # type: ignore[operator]

    assert opened == [
        (window.root, "workspace-a"),
        (window.root, "workspace-b"),
    ]


def test_cockpit_body_scroll_supports_linux_and_mousewheel_events() -> None:
    calls: list[tuple[int, str]] = []

    class FakeCanvas:
        def yview_scroll(self, units: int, mode: str) -> None:
            calls.append((units, mode))

    @dataclass
    class Event:
        num: int | None = None
        delta: int = 0

    dialog = object.__new__(McfCockpitDialog)
    dialog.body_canvas = FakeCanvas()  # type: ignore[assignment]

    assert dialog._scroll_body(Event(num=4)) == "break"  # type: ignore[arg-type]
    assert dialog._scroll_body(Event(num=5)) == "break"  # type: ignore[arg-type]
    assert dialog._scroll_body(Event(delta=240)) == "break"  # type: ignore[arg-type]
    assert dialog._scroll_body(Event(delta=-120)) == "break"  # type: ignore[arg-type]
    assert calls == [(-3, "units"), (3, "units"), (-2, "units"), (1, "units")]


def test_cockpit_auto_refresh_is_enabled_only_for_mission_control(tmp_path: Path) -> None:
    scheduled: list[tuple[int, object]] = []
    cancelled: list[str] = []

    class FakeWindow:
        def after(self, delay: int, command: object) -> str:
            scheduled.append((delay, command))
            return "job-1"

        def after_cancel(self, job: str) -> None:
            cancelled.append(job)

    dialog = object.__new__(McfCockpitDialog)
    dialog.window = FakeWindow()  # type: ignore[assignment]
    dialog._auto_refresh_job = None
    dialog.context = McfCockpitContext(
        project_root=tmp_path,
        runtime_url="https://mcf.example.test",
        mission_control_repository="leon337/multiagent-collaboration-framework",
        _mission_control_token="transient-token",
    )

    dialog._schedule_auto_refresh()
    dialog._schedule_auto_refresh()

    assert scheduled[0][0] == 3_000
    assert len(scheduled) == 2
    assert cancelled == ["job-1"]
