# TriView MCF Mission Cockpit R3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Mission Cockpit to TriView that projects canonical MCF v1.1.0 project, mission, authority, continuity and timeline information without creating a second source of truth.

**Architecture:** Keep `mcf_bridge.py` as the data boundary. Add a new `mcf_cockpit.py` presentation module with a pure model builder plus a Tk dialog and one shell installer function. `gui.py` only installs the header action; it does not own MCF parsing, credentials, authority or persistence.

**Tech Stack:** Python 3.11, dataclasses, Tkinter, pytest, existing `McfBridge`/`McfRuntimeClient`, existing TriView header extension API.

## Global Constraints

- Baseline TriView: `feat/triview-mcf-bridge-r2@f8e7a4fa99e833f3779830f5537ac4fcfb152483`.
- Baseline MCF: stable `v1.1.0@5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`.
- R3 is read-only: no writes under `.mcf`, no mission execution, no gate approval/rejection and no GitHub mutations.
- No changes to `WorkspaceSpec`, `LayoutSpec`, Workspace Hub schema or workspace persistence.
- Runtime credentials are transient only; `TRIVIEW_MCF_SESSION_TOKEN` may be read from process environment and must never appear in the cockpit model, logs, persisted files or UI.
- Resume-route calculation is out of scope for R3 and remains reserved for R5; R3 may show only canonical checkpoint references already returned by MCF.
- Project↔workspace persistent binding is out of scope for R3 and remains reserved for R4.

---

### Task 1: Cockpit presentation contract

**Files:**
- Create: `tests/test_mcf_cockpit.py`
- Create: `src/triview_workspace/mcf_cockpit.py`

**Interfaces:**
- Consumes: `McfBridgeSnapshot`, `McfRuntimeClient`, `McfBridge` from `triview_workspace.mcf_bridge`.
- Produces: `McfCockpitModel`, `McfCockpitContext`, `build_cockpit_model(snapshot)`.

- [ ] **Step 1: Write failing model tests**

```python
from pathlib import Path
from triview_workspace.mcf_bridge import (
    McfArtifactProjection,
    McfBridgeSnapshot,
    McfRepositorySnapshot,
    McfRuntimeProjection,
)
from triview_workspace.mcf_cockpit import build_cockpit_model


def test_cockpit_model_projects_mission_authority_and_continuity(tmp_path: Path) -> None:
    project = McfRepositorySnapshot(
        root=tmp_path,
        is_mcf_project=True,
        project_id="triview",
        methodology_version="v1.1.0",
        pip=McfArtifactProjection("VALID", "PROJECT_INTENT_PACKAGE", revision_id="r1"),
        prr=McfArtifactProjection("VALID", "PROJECT_REALITY_REPORT", revision_id="r1"),
        alignment=McfArtifactProjection("VALID", "INTENT_ALIGNMENT_RECEIPT", decision="PASS"),
    )
    mission = {
        "id": "mission-1",
        "state": "EXECUTING",
        "currentPhaseId": "phase-2",
        "currentAgentId": "Sofia",
        "contract": {
            "title": "Reconcile TriView",
            "riskClass": "B",
            "projectEntryMode": "ADOPT_EXISTING_PROJECT",
            "standingAuthorizations": [
                {"authorizationId": "auth-1", "status": "ACTIVE"},
                {"authorizationId": "auth-2", "status": "REVOKED"},
            ],
            "continuityCheckpointRef": {
                "path": ".mcf/checkpoints/c1.json",
                "commitSha": "abc1234",
            },
        },
    }
    runtime = McfRuntimeProjection(
        mission=mission,
        timeline={"mission": mission, "events": [
            {"eventType": "GATE_REQUIRED", "occurredAt": "2026-08-17T06:00:00Z", "agentId": "Leo", "phaseId": "phase-2"},
            {"eventType": "PHASE_STARTED", "occurredAt": "2026-08-17T06:01:00Z", "agentId": "Sofia", "phaseId": "phase-2"},
        ]},
        observability={"mission": mission, "blocked": False, "currentPhase": {"id": "phase-2", "cycle": 1}},
    )

    model = build_cockpit_model(McfBridgeSnapshot(project=project, runtime=runtime))

    assert model.project["project_id"] == "triview"
    assert model.mission["state"] == "EXECUTING"
    assert model.authority["active_standing_authorizations"] == "1"
    assert model.authority["latest_gate"] == "GATE_REQUIRED"
    assert model.continuity["checkpoint_path"] == ".mcf/checkpoints/c1.json"
    assert model.continuity["resume_route"] == "NÃO PROJETADA NO R3"
    assert model.timeline[0].event_type == "PHASE_STARTED"
```

- [ ] **Step 2: Run test and verify RED**

Run through draft-PR CI. Expected failure: `ModuleNotFoundError: triview_workspace.mcf_cockpit`.

- [ ] **Step 3: Implement minimal pure model**

Implement immutable `McfCockpitEvent`, immutable `McfCockpitModel` and `build_cockpit_model`. Parse only documented v1.1.0 response fields; malformed/missing optional values become explicit `N/A`/`AUSENTE` strings instead of guesses.

- [ ] **Step 4: Verify model tests GREEN**

Run `pytest -q tests/test_mcf_cockpit.py` via CI and then full CI.

### Task 2: Ephemeral R3 runtime context

**Files:**
- Modify: `src/triview_workspace/mcf_cockpit.py`
- Modify: `tests/test_mcf_cockpit.py`

**Interfaces:**
- Produces: `McfCockpitContext.from_environment(environ, cwd)`, `load_cockpit_model(context)`.

- [ ] **Step 1: Write failing context tests**

```python
def test_context_reads_transient_runtime_configuration_without_exposing_token(tmp_path: Path) -> None:
    context = McfCockpitContext.from_environment(
        {
            "TRIVIEW_MCF_PROJECT_ROOT": str(tmp_path),
            "TRIVIEW_MCF_MISSION_ID": "mission-1",
            "TRIVIEW_MCF_RUNTIME_URL": "https://mcf.example.test",
            "TRIVIEW_MCF_SESSION_TOKEN": "secret-token",
        },
        cwd=tmp_path.parent,
    )
    assert context.project_root == tmp_path.resolve()
    assert context.runtime_enabled is True
    assert "secret-token" not in repr(context)
```

- [ ] **Step 2: Verify RED for missing context API**

Run the focused test and confirm failure because the API does not exist.

- [ ] **Step 3: Implement context and loader**

`from_environment` defaults project root to `cwd`. Runtime access is enabled only when mission id, runtime URL and session token are all present. `load_cockpit_model` builds `McfRuntimeClient(headers={"Authorization": "Bearer <token>"})` in local scope, calls `McfBridge.inspect`, builds the presentation model, then returns only the model. The token is stored in a repr-hidden dataclass field and is never copied to presentation structures.

- [ ] **Step 4: Verify focused and full tests GREEN**

Run `pytest -q tests/test_mcf_cockpit.py` and full CI.

### Task 3: Tk read-only dialog and shell action

**Files:**
- Modify: `src/triview_workspace/mcf_cockpit.py`
- Modify: `src/triview_workspace/gui.py`
- Modify: `tests/test_mcf_cockpit.py`

**Interfaces:**
- Produces: `McfCockpitDialog`, `open_mcf_cockpit(parent)`, `install_mcf_cockpit(window)`.

- [ ] **Step 1: Write failing shell installer test**

```python
def test_installer_registers_one_read_only_mcf_header_action() -> None:
    calls = []

    class FakeWindow:
        root = object()
        def register_header_action(self, action_id, label, command, *, order=100):
            calls.append((action_id, label, command, order))

    install_mcf_cockpit(FakeWindow(), opener=lambda _parent: None)

    assert len(calls) == 1
    action_id, label, command, order = calls[0]
    assert action_id == "mcf-cockpit"
    assert label == "MCF"
    assert order == 40
    command()
```

- [ ] **Step 2: Verify RED for missing installer**

Run the focused test and confirm the installer is absent.

- [ ] **Step 3: Implement dialog and hook**

Create a dark `tk.Toplevel` using existing `ui_design` palette/fonts. Render four labeled sections (`PROJECT`, `MISSION`, `AUTHORITY`, `CONTINUITY`) and a scrollable timeline. Provide only `Atualizar` and `Fechar`; there are no approve, execute, edit or persist controls. `install_mcf_cockpit` registers a stable header action. In effective `gui.py` wrapper `WorkspaceWindow.__init__`, call `install_mcf_cockpit(self)` immediately after `super().__init__`.

- [ ] **Step 4: Verify tests and CI GREEN**

Run full CI including compile, pytest and existing X11/XTEST/Xephyr integration gates.

### Task 4: R3 architecture note and final verification

**Files:**
- Create: `docs/architecture/MCF_MISSION_COCKPIT_R3.md`

**Interfaces:**
- Documents exact R3 boundary and environment contract.

- [ ] **Step 1: Document the user-visible and security boundary**

Document the four sections, environment variables, no-persistence guarantee, absence of write controls, dependency on R2 and deferred R4/R5 responsibilities.

- [ ] **Step 2: Inspect PR diff**

Expected changed files relative to R2 branch: this plan, `mcf_cockpit.py`, `gui.py`, `test_mcf_cockpit.py`, architecture note. No persistence/domain/workspace-hub files may change.

- [ ] **Step 3: Run fresh full CI on final HEAD**

Expected: compile PASS; pytest PASS; shell validation PASS; X11 wheel PASS; XTEST PASS; Xephyr PASS.

- [ ] **Step 4: Keep stacked PR draft**

Open R3 draft PR with base `feat/triview-mcf-bridge-r2`. Do not merge or mark ready automatically.
