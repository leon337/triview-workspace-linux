# TriView × MCF R5 — Continuity / Reconcile Visual Design

**Status:** APPROVED_SCOPE — design recorded from LEANDRO's approval on 2026-08-17

**TriView baseline:** `feat/triview-mcf-binding-r4@4b92086874d51ff9470ac978b12a213419d69f7a`

**MCF semantic reference:** `main@5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`

## 1. Goal

R5 makes the TriView MCF Mission Cockpit derive and display a continuity route from canonical evidence without becoming a source of MCF authority.

The only route values are:

- `FAST_RESUME`
- `RECONCILE`
- `RECOVER_MCF_PROJECT`

R5 is orientation/read-only. It does not execute resume, reconciliation or recovery.

## 2. Source semantics

The decision contract mirrors `ContinuityRecoveryService.decideResumeRoute()` from MCF v1.1.

A route is `RECOVER_MCF_PROJECT` when any required continuity fact is missing or invalid, including:

- checkpoint absent;
- live repository state unavailable;
- authoritative records unresolved;
- methodology pin invalid;
- checkpoint integrity invalid;
- checkpoint not `TRANSFERABLE`;
- checkpoint SHA absent;
- repository identity mismatch.

A route is `FAST_RESUME` only when the checkpoint is valid/transferable and live repository state has the same repository, branch and exact checkpoint SHA.

Otherwise, explainable material drift is `RECONCILE`; unexplained material drift is `RECOVER_MCF_PROJECT`.

The checkpoint's `resumeRouteHint` is displayed as canonical historical/orientation data, but it never overrides the fresh R5 decision.

## 3. Architecture

### 3.1 Dedicated pure continuity module

Create `src/triview_workspace/mcf_continuity.py`.

It owns:

- checkpoint/ref projection and validation;
- safe canonical JSON digest verification;
- read-only live Git observation;
- conservative drift classification;
- pure route decision;
- human-readable reason codes and evidence projection.

It does not import Tkinter and does not persist anything.

### 3.2 Existing bridge remains the read composition boundary

`mcf_bridge.py` remains responsible for repository/runtime reads. R5 may extend its repository/runtime projections with the minimum information required to pass checkpoint references and continuity evidence to the pure continuity module.

R5 must not create a second MCF runtime client, event ledger, mission store or generic checkpoint engine.

### 3.3 Cockpit remains presentation-only

`mcf_cockpit.py` consumes the derived continuity decision and renders it in the existing `CONTINUITY` section. It never computes authority itself.

The current R4 binding controls remain unchanged in authority: they may only mutate TriView-owned `mcf-bindings.json`.

## 4. Canonical checkpoint resolution

Checkpoint resolution follows this precedence:

1. a valid `continuityCheckpointRef` from the current runtime mission contract;
2. if runtime is unavailable, a unique canonical checkpoint candidate for the bound `mission_id` under `.mcf/continuity/`;
3. ambiguity, missing mission id or multiple equally authoritative candidates is treated as unresolved continuity evidence, never guessed.

A runtime ref must use `artifactType=MCF_CHECKPOINT`, schema `1.1`, match the current project id, use a path contained by the project root, and point to a readable JSON object.

A local fallback candidate must have schema `1.1`, matching `projectId` and `missionId`, and is selected only when the choice is deterministic. Historical files are never deleted or rewritten.

## 5. Checkpoint integrity

R5 validates the subset required by the MCF v1.1 continuity contract:

- `schemaVersion == "1.1"`;
- non-empty `projectId`, `missionId`;
- complete `methodologyPin.version` and `methodologyPin.immutableRef`;
- `repositoryState.repository`, `branch`, `capturedAt` present;
- `repositoryState.volatile is True`;
- `checkpointSha` is either null or a 40–64 lowercase hex SHA;
- `transferability` is `TRANSFERABLE` or `BLOCKED_LOCAL_ONLY_STATE`;
- `resumeRouteHint` is one of the three MCF routes.

When a runtime checkpoint ref contains `contentDigest`, R5 verifies it as `sha256:` over canonical UTF-8 JSON with recursively sorted object keys and array order preserved. The checkpoint schema itself has no root `contentDigest`, so the entire checkpoint object is hashed.

A digest mismatch is `checkpoint_integrity_valid = false` and forces recovery.

## 6. Authoritative-record and methodology checks

R5 reuses `McfRepositorySnapshot` rather than inventing a parallel project inspector.

`authoritative_records_resolved` requires:

- the project is an MCF project;
- project identity is resolved without consistency errors;
- checkpoint project id matches the canonical project id;
- current PIP, PRR and alignment projections are not `INVALID`;
- if canonical PIP/PRR are present, their project identity remains consistent with the checkpoint.

`methodology_pin_valid` requires the checkpoint methodology pin to agree with the current valid PIP/PRR methodology pin whenever those canonical records are present. A conflict is recovery; an absent required methodology pin is recovery.

R5 does not manufacture PIP/PRR/alignment data and does not modify canonical records.

## 7. Read-only Git observation

R5 reads Git with subprocess commands only. No command may mutate repository state.

Observed live state:

- normalized repository identity from `remote.origin.url`;
- current branch;
- `HEAD` SHA;
- clean/dirty worktree state;
- ancestry relationship between checkpoint SHA and live HEAD when both commits are available locally.

Repository URL normalization must support common HTTPS and SSH GitHub forms and return an owner/repository identity. Unknown/unparseable identity is not guessed.

Git command failure, missing `.git`, missing checkpoint commit, or unknown repository identity makes live evidence insufficient and prevents `FAST_RESUME`.

## 8. Explainable drift

R5 is conservative.

`material_drift_explainable = true` only when all of the following hold:

- repository identity matches;
- checkpoint integrity/authority/methodology checks already passed;
- worktree is clean;
- both SHAs are available locally; and
- one of these relationships is provable:
  - same SHA but branch changed;
  - checkpoint SHA is an ancestor of live HEAD;
  - live HEAD is an ancestor of checkpoint SHA.

Divergent histories, missing commits or a dirty worktree are not explainable by R5 and therefore route to `RECOVER_MCF_PROJECT`.

R5 does not use chat transcript or memory as continuity evidence.

## 9. Decision projection

The pure result is a rebuildable view containing at minimum:

- `route`;
- `reason_codes`;
- checkpoint path;
- checkpoint SHA;
- live SHA;
- checkpoint branch;
- live branch;
- checkpoint repository;
- live repository;
- transferability;
- checkpoint route hint;
- worktree status;
- `authoritative_records_resolved`;
- `methodology_pin_valid`;
- `checkpoint_integrity_valid`;
- `material_drift_explainable`;
- `authority_notice = ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS`.

Reason codes are stable machine-readable strings, for example:

- `CHECKPOINT_ABSENT`
- `CHECKPOINT_REF_INVALID`
- `CHECKPOINT_DIGEST_MISMATCH`
- `CHECKPOINT_NOT_TRANSFERABLE`
- `PROJECT_ID_MISMATCH`
- `METHODOLOGY_PIN_MISMATCH`
- `LIVE_GIT_UNAVAILABLE`
- `REPOSITORY_IDENTITY_MISMATCH`
- `WORKTREE_DIRTY`
- `EXACT_LIVE_MATCH`
- `EXPLAINABLE_FORWARD_DRIFT`
- `EXPLAINABLE_BACKWARD_DRIFT`
- `EXPLAINABLE_BRANCH_DRIFT`
- `UNEXPLAINED_DIVERGENCE`.

## 10. Cockpit UI

The existing `CONTINUITY` card is upgraded to show compactly:

- `ROUTE` — the derived route;
- `REASON` — the primary reason code;
- `CHECKPOINT` — short checkpoint SHA or `AUSENTE`;
- `LIVE` — short live SHA or `INDISPONÍVEL`;
- `DRIFT` — `EXACT`, `EXPLAINABLE`, `UNEXPLAINED`, or `UNKNOWN`;
- `TRANSFERABILITY`;
- `NEXT ACTION` from canonical checkpoint when available;
- `AUTHORITY` — `ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS`.

The timeline remains unchanged. No resume/reconcile/recover action button is added in R5.

## 11. Error handling

All filesystem, JSON, digest and Git failures become evidence/reason codes in the derived view. The Cockpit must remain open and readable.

Secrets are never included in the continuity result, exception text, persistence, tests or UI.

Unsafe checkpoint paths escaping the project root are rejected.

## 12. Testing strategy

TDD is mandatory.

### Unit layer

Tests for the pure continuity module cover:

1. exact compatible state -> `FAST_RESUME`;
2. forward ancestry drift -> `RECONCILE`;
3. backward ancestry drift -> `RECONCILE`;
4. same SHA/different branch -> `RECONCILE`;
5. divergent history -> `RECOVER_MCF_PROJECT`;
6. repository mismatch -> recovery;
7. dirty worktree -> recovery;
8. missing/invalid checkpoint -> recovery;
9. blocked transferability -> recovery;
10. methodology mismatch -> recovery;
11. digest mismatch -> recovery;
12. no transcript/chat dependency;
13. no write subprocess commands;
14. safe path containment.

### Integration layer

Cockpit tests verify continuity fields are projected without Tk-specific authority logic and that R4 binding behavior remains unchanged.

### Full regression

Every GREEN commit must pass the repository CI: compile, shell validation, pytest, X11 wheel integration, XTEST device integration and Xephyr containment integration.

## 13. Non-goals

R5 does not:

- execute `FAST_RESUME`, `RECONCILE` or `RECOVER_MCF_PROJECT`;
- mutate mission/runtime state;
- approve/reject HUMAN_GATE;
- grant/revoke Standing Authorization;
- write `.mcf` artifacts;
- write Git refs, checkout branches, reset, merge, rebase, stash or commit;
- persist tokens or runtime Authorization headers;
- alter `WorkspaceSpec`, `LayoutSpec`, `WorkspaceCatalog` or `workspaces.json` schema;
- depend on previous chat transcript or assistant memory.

## 14. Acceptance criteria

R5 is complete when:

1. the decision matrix matches the MCF v1.1 `ContinuityRecoveryService` contract;
2. the decision can be rebuilt from checkpoint + authoritative project records + live Git state;
3. exact live state produces `FAST_RESUME` only under exact repository/branch/SHA match;
4. only provable, clean Git drift produces `RECONCILE`;
5. invalid, missing, ambiguous or unexplained evidence produces `RECOVER_MCF_PROJECT`;
6. the Cockpit shows route, drift and reason without exposing a mutating recovery control;
7. R4 binding and universal workspace schemas remain unchanged;
8. full CI passes on the final R5 HEAD;
9. the R5 PR remains draft/not merged until a later explicit HUMAN_GATE from LEANDRO.