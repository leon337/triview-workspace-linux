# TriView MCF Project ↔ Workspace Binding R4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist a validated reference from one TriView workspace to one MCF project context without changing the universal workspace schema or copying MCF authority into TriView.

**Architecture:** Add a dedicated atomic `mcf-bindings.json` repository beside `workspaces.json`, plus an `McfWorkspaceBinder` service that validates project identity with the existing R2 repository inspector. R3 Mission Cockpit resolves the active workspace binding first and falls back to its existing ephemeral environment contract when unbound. Only project/context references are stored; session credentials and canonical MCF artifacts/state are never persisted.

**Tech Stack:** Python 3.11+, dataclasses, pathlib, JSON atomic replacement, Tkinter, pytest, existing R2 `McfRepositoryInspector`, existing R3 `McfCockpitContext`.

## Global Constraints

- Parent TriView baseline: `feat/triview-mcf-cockpit-r3@56b1b1d64cb255a60d315d7dc87132c354466de6`.
- MCF baseline: stable `v1.1.0@5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`.
- Do not modify `WorkspaceSpec`, `LayoutSpec`, `WorkspaceCatalog`, or `workspaces.json` schema/version.
- Do not write any path under `.mcf`.
- Do not create, execute, mutate, approve, reject, grant, or revoke any MCF mission/authority operation.
- Persist only `workspace_id`, `project_root`, `project_id`, optional `mission_id`, and optional `runtime_url`.
- Never persist a session token, Authorization header, PIP/PRR contents, mission state, gate state, standing authorization, checkpoint payload, or runtime event.
- `TRIVIEW_MCF_SESSION_TOKEN` remains ephemeral process input and must not appear in binding JSON, dataclass repr, model output, logs, or documentation examples as a real value.
- R5 remains responsible for deriving or visualizing `FAST_RESUME | RECONCILE | RECOVER_MCF_PROJECT`.

---

### Task 1: Dedicated binding repository and validated binder

**Files:**
- Create: `src/triview_workspace/mcf_binding.py`
- Test: `tests/test_mcf_binding.py`

**Interfaces:**
- Produces: `McfWorkspaceBinding`, `McfBindingRepository`, `McfWorkspaceBinder`, `McfBindingError`.
- Consumes: `McfRepositoryInspector.inspect(project_root)` from R2.

- [ ] **Step 1: Write failing persistence and validation tests**

Cover exact behaviors:

```python
binding = binder.bind(
    "workspace-a",
    project_root,
    mission_id="mission-1",
    runtime_url="https://mcf.example.test",
)
assert binding.workspace_id == "workspace-a"
assert binding.project_id == "project-a"
assert repository.get("workspace-a") == binding
```

Also assert that serialized JSON is schema version 1, contains only the five allowed binding fields, never contains `token`, `authorization`, PIP/PRR or authority fields, replaces an existing binding by workspace id, can unbind one workspace, quarantines malformed JSON via `load_or_empty()`, rejects non-MCF roots, and rejects a persisted binding whose canonical project id no longer matches.

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_mcf_binding.py -q`

Expected: collection fails because `triview_workspace.mcf_binding` does not exist.

- [ ] **Step 3: Implement the minimal repository**

Use:

```python
BINDING_SCHEMA_VERSION = 1

@dataclass(frozen=True, slots=True)
class McfWorkspaceBinding:
    workspace_id: str
    project_root: Path
    project_id: str
    mission_id: str | None = None
    runtime_url: str | None = None
```

`McfBindingRepository.default_path()` resolves to the same XDG data root as workspace persistence but uses `triview-workspace/mcf-bindings.json`. Writes use tempfile + flush + fsync + `os.replace`, with strict whitelist decoding and one binding per workspace id.

- [ ] **Step 4: Implement validated binder**

`McfWorkspaceBinder.bind()` inspects the requested root, requires `is_mcf_project` and a non-empty canonical `project_id`, then persists the reference. `resolve()` reloads by workspace id and re-inspects the root; if project identity differs, raise `McfBindingError` instead of silently rebinding. `unbind()` removes only the TriView reference.

- [ ] **Step 5: Run GREEN**

Run: `pytest tests/test_mcf_binding.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/triview_workspace/mcf_binding.py tests/test_mcf_binding.py
git commit -m "feat: add validated MCF workspace binding store"
```

### Task 2: Resolve Cockpit context from the active workspace binding

**Files:**
- Modify: `src/triview_workspace/mcf_cockpit.py`
- Modify: `tests/test_mcf_cockpit.py`

**Interfaces:**
- Consumes: `McfWorkspaceBinder.resolve(workspace_id)` and `McfBindingRepository`.
- Produces: `McfCockpitContext.for_workspace(...)`; `open_mcf_cockpit(parent, workspace_id=...)`; active-workspace-aware header action.

- [ ] **Step 1: Add failing context-resolution tests**

Assert that a saved binding overrides `TRIVIEW_MCF_PROJECT_ROOT`, `TRIVIEW_MCF_MISSION_ID`, and `TRIVIEW_MCF_RUNTIME_URL` for that workspace, while `TRIVIEW_MCF_SESSION_TOKEN` is still taken only from the process environment. Assert unbound workspaces retain R3 environment/cwd behavior. Assert `install_mcf_cockpit()` resolves `window.workspace.id` at click time rather than installation time.

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_mcf_cockpit.py -q`

Expected: FAIL because binding-aware context/opening does not exist.

- [ ] **Step 3: Implement binding-aware context**

Add `workspace_id` and `binding_persisted` non-secret presentation context fields. `for_workspace()` asks the binder for a binding; when present, use its project root/mission/runtime URL and only read the session token from environment. When absent, delegate to the existing R3 environment behavior.

- [ ] **Step 4: Preserve GUI lifecycle contract**

Do not override the effective RC4 constructor. Keep the existing `_build_header` hook and make its registered command capture the window object so `workspace.id` is read at click time after workspace switches.

- [ ] **Step 5: Run GREEN**

Run: `pytest tests/test_mcf_binding.py tests/test_mcf_cockpit.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/triview_workspace/mcf_cockpit.py tests/test_mcf_cockpit.py
git commit -m "feat: resolve MCF cockpit from workspace binding"
```

### Task 3: Safe bind/unbind controls in Mission Cockpit

**Files:**
- Modify: `src/triview_workspace/mcf_cockpit.py`
- Modify: `tests/test_mcf_cockpit.py`

**Interfaces:**
- Consumes: current `McfCockpitContext` and `McfWorkspaceBinder.bind/unbind`.
- Produces: TriView-only `Vincular` / `Desvincular` actions; no MCF mutation.

- [ ] **Step 1: Add failing action tests without requiring a real Tk display**

Extract action helpers that can be tested with fake binder/context objects. Binding persists the current project root plus optional mission/runtime references for the current workspace. Unbinding deletes only the binding. Verify no method receives or serializes the session token.

- [ ] **Step 2: Run RED**

Run: `pytest tests/test_mcf_cockpit.py -q`

Expected: FAIL because bind/unbind helpers are absent.

- [ ] **Step 3: Implement minimal controls**

Add `Vincular workspace` when the current workspace is unbound and `Desvincular workspace` when bound. After either operation, rebuild context and refresh. Errors render through the existing safe error surface with token redaction. No confirmation or control is added for mission mutation, HUMAN_GATE, authorization, or `.mcf` writes.

- [ ] **Step 4: Run GREEN**

Run: `pytest tests/test_mcf_binding.py tests/test_mcf_cockpit.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/triview_workspace/mcf_cockpit.py tests/test_mcf_cockpit.py
git commit -m "feat: manage TriView MCF workspace bindings"
```

### Task 4: Architecture boundary and full regression verification

**Files:**
- Create: `docs/architecture/MCF_WORKSPACE_BINDING_R4.md`

**Interfaces:**
- Documents the five-field persisted contract, separate file ownership, credential boundary, identity revalidation, and R5 handoff.

- [ ] **Step 1: Document the exact persistence contract**

State that `mcf-bindings.json` belongs to TriView, not MCF; MCF remains source of truth; binding deletion never deletes MCF data; workspace deletion may leave an inert orphan binding but cannot affect MCF authority; cleanup/reconciliation is separate from canonical project state.

- [ ] **Step 2: Inspect PR diff**

Expected changed scope: plan, `mcf_binding.py`, `mcf_cockpit.py`, binding/cockpit tests, architecture doc. No changes to `domain/models.py` or `infrastructure/persistence.py`.

- [ ] **Step 3: Run full CI**

Expected: compile, shell validation, pytest, X11 wheel integration, XTEST integration, and Xephyr containment all PASS.

- [ ] **Step 4: Keep PR draft**

Do not merge automatically. Record RED, GREEN and any regression/recovery evidence in the draft PR body.
