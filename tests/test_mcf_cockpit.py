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
from triview_workspace.mcf_cockpit import (
    McfCockpitContext,
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
    assert model.timeline == ()


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
            "TRIVIEW_MCF_REGISTRY_ROOT": str(tmp_path / "mcf-registry"),
        },
        cwd=tmp_path.parent,
    )

    assert context.project_root == tmp_path.resolve()
    assert context.mission_id == "mission-1"
    assert context.runtime_url == "https://mcf.example.test/"
    assert context.runtime_enabled is True
    assert context.context_runtime_enabled is True
    assert context.registry_root == (tmp_path / "mcf-registry").resolve()
    assert "secret-token" not in repr(context)


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
        },
        cwd=tmp_path,
    )

    assert context.workspace_id == "workspace-a"
    assert context.binding_persisted is True
    assert context.project_root == bound_root.resolve()
    assert context.mission_id == "bound-mission"
    assert context.runtime_url == "https://bound.example.test/"
    assert context.runtime_enabled is True
    assert "ephemeral-token" not in repr(context)


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
