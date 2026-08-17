# TriView × MCF R5 Continuity / Reconcile Visual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Derive and display the MCF v1.1 continuity route (`FAST_RESUME | RECONCILE | RECOVER_MCF_PROJECT`) from canonical checkpoint/project evidence plus read-only live Git state, without executing or persisting recovery authority.

**Architecture:** Add one focused `mcf_continuity.py` module that owns checkpoint validation, read-only Git observation and the pure route decision. Reuse `McfRepositorySnapshot`/`McfRuntimeProjection` from the existing bridge, then pass one rebuildable continuity decision into `mcf_cockpit.py` for display. Keep R4 binding storage and universal workspace schemas untouched.

**Tech Stack:** Python 3.11+, stdlib (`dataclasses`, `hashlib`, `json`, `pathlib`, `subprocess`, `urllib.parse`), pytest, existing Tkinter UI, GitHub Actions CI.

## Global Constraints

- TriView baseline is exactly `feat/triview-mcf-binding-r4@4b92086874d51ff9470ac978b12a213419d69f7a`.
- MCF decision semantics mirror `ContinuityRecoveryService.decideResumeRoute()` at `leon337/multiagent-collaboration-framework@5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`.
- No R5 operation may write `.mcf`, mutate the MCF runtime, mutate Git state, approve/reject HUMAN_GATE, or grant/revoke Standing Authorization.
- No recovery/resume/reconcile execution button is added in R5.
- `TRIVIEW_MCF_SESSION_TOKEN` remains process-only and must never enter continuity results, persistence, logs or tests.
- R4 `mcf-bindings.json` behavior stays unchanged.
- `WorkspaceSpec`, `LayoutSpec`, `WorkspaceCatalog`, `src/triview_workspace/domain/models.py`, `src/triview_workspace/infrastructure/persistence.py` and the `workspaces.json` schema stay unchanged.
- TDD is mandatory: every production behavior starts from a verified failing test.
- Every GREEN implementation commit must run the full repository CI before the next production task.

---

### Task 1: Pure MCF v1.1 resume-route decision

**Files:**
- Create: `src/triview_workspace/mcf_continuity.py`
- Create: `tests/test_mcf_continuity_decision.py`

**Interfaces:**
- Consumes: no I/O; only explicit facts.
- Produces:
  - `McfResumeRoute = Literal["FAST_RESUME", "RECONCILE", "RECOVER_MCF_PROJECT"]`
  - `McfDriftStatus = Literal["EXACT", "EXPLAINABLE", "UNEXPLAINED", "UNKNOWN"]`
  - `McfLiveRepositoryState(repository: str, branch: str, head_sha: str, worktree_clean: bool)`
  - `McfResumeDecisionInput(...)`
  - `McfRouteDecision(route, reason_codes, drift)`
  - `decide_resume_route(input: McfResumeDecisionInput) -> McfRouteDecision`

- [ ] **Step 1: Write failing tests for the official decision matrix**

Create `tests/test_mcf_continuity_decision.py` with focused tests equivalent to the MCF v1.1 contract:

```python
from triview_workspace.mcf_continuity import (
    McfLiveRepositoryState,
    McfResumeDecisionInput,
    decide_resume_route,
)


def _input(**overrides: object) -> McfResumeDecisionInput:
    values: dict[str, object] = {
        "checkpoint_available": True,
        "live_repository_state": McfLiveRepositoryState(
            repository="leon337/project",
            branch="feat/r5",
            head_sha="a" * 40,
            worktree_clean=True,
        ),
        "authoritative_records_resolved": True,
        "methodology_pin_valid": True,
        "checkpoint_integrity_valid": True,
        "transferability": "TRANSFERABLE",
        "checkpoint_repository": "leon337/project",
        "checkpoint_branch": "feat/r5",
        "checkpoint_sha": "a" * 40,
        "material_drift_explainable": False,
        "drift_reason": None,
    }
    values.update(overrides)
    return McfResumeDecisionInput(**values)  # type: ignore[arg-type]


def test_exact_compatible_live_state_is_fast_resume() -> None:
    decision = decide_resume_route(_input())
    assert decision.route == "FAST_RESUME"
    assert decision.drift == "EXACT"
    assert decision.reason_codes == ("EXACT_LIVE_MATCH",)


def test_explainable_drift_is_reconcile() -> None:
    decision = decide_resume_route(
        _input(
            live_repository_state=McfLiveRepositoryState(
                repository="leon337/project",
                branch="feat/r5",
                head_sha="b" * 40,
                worktree_clean=True,
            ),
            material_drift_explainable=True,
            drift_reason="EXPLAINABLE_FORWARD_DRIFT",
        )
    )
    assert decision.route == "RECONCILE"
    assert decision.drift == "EXPLAINABLE"
    assert decision.reason_codes == ("EXPLAINABLE_FORWARD_DRIFT",)


def test_unexplained_drift_is_recovery() -> None:
    decision = decide_resume_route(
        _input(
            live_repository_state=McfLiveRepositoryState(
                repository="leon337/project",
                branch="feat/r5",
                head_sha="c" * 40,
                worktree_clean=True,
            )
        )
    )
    assert decision.route == "RECOVER_MCF_PROJECT"
    assert decision.drift == "UNEXPLAINED"
    assert decision.reason_codes == ("UNEXPLAINED_DIVERGENCE",)


def test_missing_authority_integrity_or_transferability_forces_recovery() -> None:
    cases = (
        ({"checkpoint_available": False}, "CHECKPOINT_ABSENT"),
        ({"live_repository_state": None}, "LIVE_GIT_UNAVAILABLE"),
        ({"authoritative_records_resolved": False}, "AUTHORITATIVE_RECORDS_UNRESOLVED"),
        ({"methodology_pin_valid": False}, "METHODOLOGY_PIN_MISMATCH"),
        ({"checkpoint_integrity_valid": False}, "CHECKPOINT_INTEGRITY_INVALID"),
        ({"transferability": "BLOCKED_LOCAL_ONLY_STATE"}, "CHECKPOINT_NOT_TRANSFERABLE"),
        ({"checkpoint_sha": None}, "CHECKPOINT_SHA_ABSENT"),
    )
    for overrides, expected_reason in cases:
        decision = decide_resume_route(_input(**overrides))
        assert decision.route == "RECOVER_MCF_PROJECT"
        assert expected_reason in decision.reason_codes


def test_repository_identity_mismatch_forces_recovery() -> None:
    decision = decide_resume_route(
        _input(
            live_repository_state=McfLiveRepositoryState(
                repository="other/project",
                branch="feat/r5",
                head_sha="a" * 40,
                worktree_clean=True,
            )
        )
    )
    assert decision.route == "RECOVER_MCF_PROJECT"
    assert decision.reason_codes == ("REPOSITORY_IDENTITY_MISMATCH",)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
pytest tests/test_mcf_continuity_decision.py -q
```

Expected: collection/import failure because `triview_workspace.mcf_continuity` does not exist yet. Record the CI run as RED evidence before production code.

- [ ] **Step 3: Implement the minimum pure decision API**

Create `src/triview_workspace/mcf_continuity.py` with the public types and decision function. The decision order must match MCF v1.1:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

McfResumeRoute = Literal["FAST_RESUME", "RECONCILE", "RECOVER_MCF_PROJECT"]
McfDriftStatus = Literal["EXACT", "EXPLAINABLE", "UNEXPLAINED", "UNKNOWN"]


@dataclass(frozen=True, slots=True)
class McfLiveRepositoryState:
    repository: str
    branch: str
    head_sha: str
    worktree_clean: bool


@dataclass(frozen=True, slots=True)
class McfResumeDecisionInput:
    checkpoint_available: bool
    live_repository_state: McfLiveRepositoryState | None
    authoritative_records_resolved: bool
    methodology_pin_valid: bool
    checkpoint_integrity_valid: bool
    transferability: str | None
    checkpoint_repository: str | None
    checkpoint_branch: str | None
    checkpoint_sha: str | None
    material_drift_explainable: bool
    drift_reason: str | None = None


@dataclass(frozen=True, slots=True)
class McfRouteDecision:
    route: McfResumeRoute
    reason_codes: tuple[str, ...]
    drift: McfDriftStatus


def decide_resume_route(input: McfResumeDecisionInput) -> McfRouteDecision:
    failures: list[str] = []
    if not input.checkpoint_available:
        failures.append("CHECKPOINT_ABSENT")
    if input.live_repository_state is None:
        failures.append("LIVE_GIT_UNAVAILABLE")
    if not input.authoritative_records_resolved:
        failures.append("AUTHORITATIVE_RECORDS_UNRESOLVED")
    if not input.methodology_pin_valid:
        failures.append("METHODOLOGY_PIN_MISMATCH")
    if not input.checkpoint_integrity_valid:
        failures.append("CHECKPOINT_INTEGRITY_INVALID")
    if input.transferability != "TRANSFERABLE":
        failures.append("CHECKPOINT_NOT_TRANSFERABLE")
    if input.checkpoint_sha is None:
        failures.append("CHECKPOINT_SHA_ABSENT")
    if failures:
        return McfRouteDecision("RECOVER_MCF_PROJECT", tuple(failures), "UNKNOWN")

    live = input.live_repository_state
    assert live is not None
    if input.checkpoint_repository != live.repository:
        return McfRouteDecision(
            "RECOVER_MCF_PROJECT",
            ("REPOSITORY_IDENTITY_MISMATCH",),
            "UNEXPLAINED",
        )
    if input.checkpoint_branch == live.branch and input.checkpoint_sha == live.head_sha:
        return McfRouteDecision("FAST_RESUME", ("EXACT_LIVE_MATCH",), "EXACT")
    if input.material_drift_explainable:
        return McfRouteDecision(
            "RECONCILE",
            (input.drift_reason or "EXPLAINABLE_DRIFT",),
            "EXPLAINABLE",
        )
    return McfRouteDecision(
        "RECOVER_MCF_PROJECT",
        ("UNEXPLAINED_DIVERGENCE",),
        "UNEXPLAINED",
    )
```

Do not add filesystem, Git or Tk behavior in Task 1.

- [ ] **Step 4: Run focused tests and full CI; verify GREEN**

Run the focused test locally when available, then push the commit and require the repository CI to pass compile, shell, pytest, X11 wheel, XTEST and Xephyr.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/triview_workspace/mcf_continuity.py tests/test_mcf_continuity_decision.py
git commit -m "feat: add MCF continuity route decision"
```

---

### Task 2: Canonical checkpoint and authoritative evidence inspection

**Files:**
- Modify: `src/triview_workspace/mcf_continuity.py`
- Create: `tests/test_mcf_continuity_checkpoint.py`

**Interfaces:**
- Consumes:
  - `McfRepositorySnapshot` and `McfRuntimeProjection` from `mcf_bridge.py`.
  - `mission_id` from `McfCockpitContext`.
- Produces:
  - `McfCheckpointProjection`
  - `McfCheckpointEvidence`
  - `McfCheckpointInspector.inspect(...)`
  - `canonical_json_digest(payload: Mapping[str, object]) -> str`

- [ ] **Step 1: Write failing checkpoint/evidence tests**

Tests must build canonical `.mcf/continuity/*.json` fixtures under `tmp_path` and cover runtime-ref precedence, local fallback, safe path containment, digest mismatch, mission/project mismatch, PIP/PRR/alignment requirements and methodology pin mismatch.

Use a canonical checkpoint fixture shaped like the MCF v1.1 schema:

```python

def _checkpoint(*, project_id: str = "project-1", mission_id: str = "mission-1") -> dict[str, object]:
    return {
        "schemaVersion": "1.1",
        "projectId": project_id,
        "missionId": mission_id,
        "methodologyPin": {
            "version": "v1.1.0",
            "immutableRef": "5d79f488407c77f7b9f21ecfefb41ddfb3a52aef",
        },
        "alignedPipRef": {
            "artifactType": "PROJECT_INTENT_PACKAGE",
            "schemaVersion": "1.0",
            "projectId": project_id,
            "revisionId": "pip-r1",
            "path": ".mcf/intent/pip-r1.json",
        },
        "projectRealityReportRef": {
            "artifactType": "PROJECT_REALITY_REPORT",
            "schemaVersion": "1.0",
            "projectId": project_id,
            "revisionId": "prr-r1",
            "path": ".mcf/reality/prr-r1.json",
        },
        "missionContractRef": f".mcf/missions/{mission_id}.json",
        "repositoryState": {
            "repository": "leon337/project",
            "branch": "feat/r5",
            "checkpointSha": "a" * 40,
            "capturedAt": "2026-08-17T08:00:00Z",
            "volatile": True,
        },
        "resumeRouteHint": "FAST_RESUME",
        "transferability": "TRANSFERABLE",
        "objetivo": "Continue mission",
        "estado": "EM_EXECUCAO",
        "ultimo_sucesso": "Checkpoint persisted",
        "falha_atual": "nenhuma",
        "classe_da_falha": "NENHUMA",
        "efeito_confirmado": "No failure effect",
        "recuperacao_escolhida": "nenhuma",
        "proxima_acao": "Continue from canonical checkpoint",
        "destinatario": "MESTRE",
        "artefatos": [{"tipo": "commit", "referencia": "a" * 40}],
    }
```

Required assertions include:

```python
assert evidence.checkpoint is not None
assert evidence.checkpoint_integrity_valid is True
assert evidence.authoritative_records_resolved is True
assert evidence.methodology_pin_valid is True
assert evidence.checkpoint.next_action == "Continue from canonical checkpoint"
```

and negative cases:

```python
assert "CHECKPOINT_DIGEST_MISMATCH" in evidence.reason_codes
assert "MISSION_ID_MISMATCH" in evidence.reason_codes
assert "PROJECT_ID_MISMATCH" in evidence.reason_codes
assert "AUTHORITATIVE_RECORDS_UNRESOLVED" in evidence.reason_codes
assert "METHODOLOGY_PIN_MISMATCH" in evidence.reason_codes
assert "UNSAFE_CHECKPOINT_PATH" in evidence.reason_codes
```

- [ ] **Step 2: Push tests and verify RED**

Expected failures: missing `McfCheckpointInspector`, checkpoint projection and digest helpers. Confirm compile remains healthy and failure is isolated to pytest.

- [ ] **Step 3: Implement checkpoint/ref parsing and digest validation**

Add focused dataclasses:

```python
@dataclass(frozen=True, slots=True)
class McfCheckpointProjection:
    path: str
    project_id: str
    mission_id: str
    methodology_version: str
    methodology_ref: str
    repository: str
    branch: str
    checkpoint_sha: str | None
    captured_at: str
    transferability: str
    resume_route_hint: McfResumeRoute
    next_action: str
    responsible_agent: str
    aligned_pip_ref: Mapping[str, object] | None
    project_reality_report_ref: Mapping[str, object] | None


@dataclass(frozen=True, slots=True)
class McfCheckpointEvidence:
    checkpoint: McfCheckpointProjection | None
    checkpoint_integrity_valid: bool
    authoritative_records_resolved: bool
    methodology_pin_valid: bool
    reason_codes: tuple[str, ...]
```

Implement canonical digest with recursive key sorting and array order preservation:

```python
def _sort_json(value: object) -> object:
    if isinstance(value, dict):
        return {key: _sort_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sort_json(item) for item in value]
    return value


def canonical_json_digest(payload: Mapping[str, object]) -> str:
    canonical = json.dumps(
        _sort_json(dict(payload)),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Implement safe path resolution with `Path.resolve()` and `relative_to(project_root)`; reject any escaping path.

For runtime refs, validate `artifactType`, `schemaVersion`, `projectId`, path and optional digest before accepting the referenced file.

For local fallback, inspect only `.mcf/continuity/*.json`, keep valid schema-1.1 candidates matching `mission_id`, parse `capturedAt`, choose the newest; a top timestamp tie becomes `CHECKPOINT_AMBIGUOUS`.

Parse display aliases conservatively:

```python
next_action = str(payload.get("nextAction") or payload.get("proxima_acao") or "").strip()
responsible_agent = str(payload.get("responsibleAgent") or payload.get("destinatario") or "").strip()
```

For authoritative records require current PIP=`VALID`, PRR=`VALID`, alignment=`VALID/PASS`, all project ids equal, and checkpoint mission/project identity equal the current context. Compare checkpoint PIP/PRR refs to selected `revision_id` when refs exist.

For methodology require checkpoint version/ref to equal both valid PIP and PRR methodology pins.

- [ ] **Step 4: Run focused tests and full CI; verify GREEN**

The full CI must pass before Task 3.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/triview_workspace/mcf_continuity.py tests/test_mcf_continuity_checkpoint.py
git commit -m "feat: inspect canonical MCF continuity evidence"
```

---

### Task 3: Read-only Git state and conservative drift classification

**Files:**
- Modify: `src/triview_workspace/mcf_continuity.py`
- Create: `tests/test_mcf_continuity_git.py`

**Interfaces:**
- Produces:
  - `McfGitEvidence(live_state, material_drift_explainable, drift_reason, reason_codes)`
  - `McfGitObserver.observe(root: Path, checkpoint: McfCheckpointProjection) -> McfGitEvidence`
  - `normalize_github_repository(remote_url: str) -> str | None`

- [ ] **Step 1: Write failing Git-observer tests with an injected runner**

Use a fake runner recording argument tuples. Cover HTTPS/SSH normalization, exact state, clean forward/backward/branch drift, divergent history, dirty worktree, missing origin, missing checkpoint commit and Git failure.

The tests must assert every invoked Git command is read-only:

```python
for args in calls:
    assert args[0] == "git"
    assert not {
        "checkout", "switch", "reset", "merge", "rebase", "stash", "commit", "add", "clean", "pull", "push"
    }.intersection(args)
```

Expected route inputs from the observer:

```python
assert evidence.material_drift_explainable is True
assert evidence.drift_reason == "EXPLAINABLE_FORWARD_DRIFT"
```

Dirty or divergent state:

```python
assert evidence.material_drift_explainable is False
assert "WORKTREE_DIRTY" in evidence.reason_codes
# or UNEXPLAINED_DIVERGENCE for clean unrelated histories
```

- [ ] **Step 2: Push tests and verify RED**

Expected: missing `McfGitObserver` and normalization helper.

- [ ] **Step 3: Implement the minimal read-only Git adapter**

Use `subprocess.run(..., shell=False, capture_output=True, text=True, timeout=3, check=False)` through an injectable runner. Commands are limited to:

```text
git -C <root> config --get remote.origin.url
git -C <root> rev-parse --abbrev-ref HEAD
git -C <root> rev-parse HEAD
git -C <root> status --porcelain
git -C <root> cat-file -e <checkpointSha>^{commit}
git -C <root> merge-base --is-ancestor <checkpointSha> <headSha>
git -C <root> merge-base --is-ancestor <headSha> <checkpointSha>
```

Normalize:

- `https://github.com/owner/repo.git` -> `owner/repo`
- `git@github.com:owner/repo.git` -> `owner/repo`
- `ssh://git@github.com/owner/repo.git` -> `owner/repo`

Classification order:

1. Git/unparseable origin/missing commit -> unavailable/unexplained evidence.
2. Dirty worktree -> `WORKTREE_DIRTY`, not explainable.
3. Same SHA + different branch -> `EXPLAINABLE_BRANCH_DRIFT`.
4. checkpoint ancestor of HEAD -> `EXPLAINABLE_FORWARD_DRIFT`.
5. HEAD ancestor of checkpoint -> `EXPLAINABLE_BACKWARD_DRIFT`.
6. neither ancestry relation -> `UNEXPLAINED_DIVERGENCE`.

Exact branch+SHA is left for the pure Task 1 decision to classify as `FAST_RESUME`.

- [ ] **Step 4: Run focused tests and full CI; verify GREEN**

Require all current CI stages green.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/triview_workspace/mcf_continuity.py tests/test_mcf_continuity_git.py
git commit -m "feat: derive MCF continuity drift from read-only git"
```

---

### Task 4: Compose R5 evidence and project it in Mission Cockpit

**Files:**
- Modify: `src/triview_workspace/mcf_continuity.py`
- Modify: `src/triview_workspace/mcf_cockpit.py`
- Modify: `tests/test_mcf_cockpit.py`
- Create: `tests/test_mcf_continuity_analysis.py`

**Interfaces:**
- Produces:
  - `McfContinuityDecision`
  - `McfContinuityAnalyzer.analyze(...) -> McfContinuityDecision`
  - `build_cockpit_model(snapshot, continuity=...)`

- [ ] **Step 1: Write failing analyzer tests**

Compose fake `McfRepositorySnapshot`, `McfRuntimeProjection`, checkpoint inspector and Git observer outputs. Assert analyzer passes exact facts to `decide_resume_route` and preserves evidence fields:

```python
assert decision.route == "FAST_RESUME"
assert decision.checkpoint_sha == "a" * 40
assert decision.live_sha == "a" * 40
assert decision.transferability == "TRANSFERABLE"
assert decision.authority_notice == "ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS"
```

Also test no mission/checkpoint, dirty worktree and explainable drift.

- [ ] **Step 2: Write failing Cockpit projection tests**

Update `tests/test_mcf_cockpit.py` so the continuity card expects R5 values instead of `NÃO PROJETADA NO R3`:

```python
assert model.continuity["route"] == "RECONCILE"
assert model.continuity["reason"] == "EXPLAINABLE_FORWARD_DRIFT"
assert model.continuity["checkpoint"] == "aaaaaaaaaaaa"
assert model.continuity["live"] == "bbbbbbbbbbbb"
assert model.continuity["drift"] == "EXPLAINABLE"
assert model.continuity["transferability"] == "TRANSFERABLE"
assert model.continuity["authority"] == "ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS"
```

Keep existing Project/Mission/Authority/Timeline and R4 binding assertions.

- [ ] **Step 3: Push tests and verify RED**

Expected failures: analyzer/decision object and new Cockpit `continuity` projection do not exist yet.

- [ ] **Step 4: Implement `McfContinuityAnalyzer`**

Compose Task 2 + Task 3 without new authority:

```python
@dataclass(frozen=True, slots=True)
class McfContinuityDecision:
    route: McfResumeRoute
    reason_codes: tuple[str, ...]
    drift: McfDriftStatus
    checkpoint_path: str | None
    checkpoint_sha: str | None
    live_sha: str | None
    checkpoint_branch: str | None
    live_branch: str | None
    checkpoint_repository: str | None
    live_repository: str | None
    transferability: str | None
    checkpoint_route_hint: McfResumeRoute | None
    worktree_status: str
    authoritative_records_resolved: bool
    methodology_pin_valid: bool
    checkpoint_integrity_valid: bool
    material_drift_explainable: bool
    next_action: str
    authority_notice: str = "ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS"
```

The analyzer:

1. resolves checkpoint evidence;
2. observes Git only when a checkpoint exists;
3. builds `McfResumeDecisionInput`;
4. calls the pure decision function;
5. combines decision + evidence into `McfContinuityDecision`.

No exception escapes for normal missing/invalid evidence; convert it to recovery reason codes.

- [ ] **Step 5: Integrate with `load_cockpit_model`**

After the existing `McfBridge.inspect(...)`, derive continuity:

```python
continuity = McfContinuityAnalyzer().analyze(
    root=context.project_root,
    project=snapshot.project,
    runtime=snapshot.runtime,
    mission_id=context.mission_id,
)
return build_cockpit_model(snapshot, continuity=continuity)
```

Keep runtime token handling exactly where it is today.

Change `build_cockpit_model` to accept the derived decision as an optional keyword-only argument for testability. Project continuity fields with one helper:

```python
def _short_sha(value: str | None, fallback: str) -> str:
    return value[:12] if value else fallback
```

and:

```python
continuity_fields = {
    "route": continuity.route,
    "reason": continuity.reason_codes[0] if continuity.reason_codes else "N/A",
    "checkpoint": _short_sha(continuity.checkpoint_sha, "AUSENTE"),
    "live": _short_sha(continuity.live_sha, "INDISPONÍVEL"),
    "drift": continuity.drift,
    "transferability": continuity.transferability or "N/A",
    "next_action": continuity.next_action or "N/A",
    "authority": continuity.authority_notice,
}
```

Do not add mutating continuity buttons.

- [ ] **Step 6: Run focused tests and full CI; verify GREEN**

Require all current CI stages green before documentation.

- [ ] **Step 7: Commit Task 4**

```bash
git add src/triview_workspace/mcf_continuity.py src/triview_workspace/mcf_cockpit.py tests/test_mcf_continuity_analysis.py tests/test_mcf_cockpit.py
git commit -m "feat: project MCF continuity route in cockpit"
```

---

### Task 5: Boundary documentation, diff audit and final R5 gate

**Files:**
- Create: `docs/architecture/MCF_CONTINUITY_R5.md`
- Modify: PR body only; no production code expected.

**Interfaces:**
- Documents the exact MCF source semantics, evidence rules and non-authority boundary.

- [ ] **Step 1: Write the architecture boundary document**

Record:

- TriView R4 baseline and R5 HEAD;
- MCF semantic reference `5d79f488...`;
- official route matrix;
- checkpoint resolution precedence;
- digest convention;
- Git read-only command allowlist;
- explainable drift definition;
- reason-code vocabulary;
- UI fields;
- explicit list of forbidden writes/actions;
- TDD RED/GREEN CI run IDs.

- [ ] **Step 2: Commit documentation**

```bash
git add docs/architecture/MCF_CONTINUITY_R5.md
git commit -m "docs: define R5 continuity boundary"
```

- [ ] **Step 3: Run fresh final CI on documentation HEAD**

Require success for compile, shell validation, pytest, X11 wheel, XTEST and Xephyr. Do not reuse an earlier GREEN run as final evidence.

- [ ] **Step 4: Audit branch scope against R4**

Compare exact refs:

```text
base = 4b92086874d51ff9470ac978b12a213419d69f7a
head = <final R5 HEAD>
```

Expected production scope is limited to `mcf_continuity.py` and `mcf_cockpit.py`; plus tests/spec/plan/architecture docs. Confirm there are no modifications to universal workspace domain/persistence schemas or R4 binding storage.

- [ ] **Step 5: Update draft PR evidence without merging**

The R5 PR must target `feat/triview-mcf-binding-r4`, remain `draft=true`, `merged=false`, and list each RED/GREEN commit/run plus the final CI run.

- [ ] **Step 6: HUMAN_GATE**

Report `R5 = ENTREGUE / CI PASS / DRAFT / NOT MERGED` and ask LEANDRO for explicit approval before any merge or next mutating continuity stage.