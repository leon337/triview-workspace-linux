# TriView × MCF — R5 Continuity / Reconcile Visual

**Status:** implementation complete; final documentation CI pending at this commit.

**TriView baseline:** `feat/triview-mcf-binding-r4@4b92086874d51ff9470ac978b12a213419d69f7a`

**R5 implementation HEAD before this document:** `7d4c2da7abc4fb3e2ffb5df73c1848e903fd98ce`

**MCF semantic reference:** `leon337/multiagent-collaboration-framework@5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`

## 1. Purpose

R5 turns the existing read-only MCF Mission Cockpit into a continuity-orientation surface. It derives exactly one of the MCF v1.1 routes:

- `FAST_RESUME`
- `RECONCILE`
- `RECOVER_MCF_PROJECT`

The route is a projection of canonical evidence. It is not an instruction executor and does not itself become MCF authority.

The fixed authority notice is:

`ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS`

## 2. Official MCF v1.1 route matrix

R5 mirrors the decision order of `ContinuityRecoveryService.decideResumeRoute()` from the MCF v1.1 semantic reference.

`RECOVER_MCF_PROJECT` is selected when any required fact is absent or invalid, including:

1. checkpoint absent;
2. live repository state unavailable;
3. authoritative project records unresolved;
4. methodology pin invalid;
5. checkpoint integrity invalid;
6. checkpoint not `TRANSFERABLE`;
7. checkpoint SHA absent;
8. live repository identity differs from checkpoint repository identity.

`FAST_RESUME` is selected only after the checks above pass and all three live repository facts match exactly:

- same repository;
- same branch;
- same SHA.

If the required evidence is valid but the live state differs, only provable material drift may select `RECONCILE`. Otherwise R5 selects `RECOVER_MCF_PROJECT`.

The checkpoint `resumeRouteHint` is retained as historical/orientation data and never overrides the fresh derived route.

## 3. Architectural boundary

R5 adds one dedicated module:

`src/triview_workspace/mcf_continuity.py`

It owns:

- the pure route decision;
- checkpoint resolution and validation;
- canonical JSON digest validation;
- authoritative PIP/PRR/alignment checks;
- methodology-pin checks;
- read-only Git observation;
- conservative drift classification;
- composition into `McfContinuityDecision`.

`src/triview_workspace/mcf_cockpit.py` remains presentation-only. It consumes the already-derived `McfContinuityDecision` and renders it in the existing `CONTINUITY` card.

R5 does not change:

- `src/triview_workspace/mcf_binding.py`;
- `src/triview_workspace/domain/models.py`;
- `src/triview_workspace/infrastructure/persistence.py`;
- `src/triview_workspace/gui.py`;
- `WorkspaceSpec`;
- `LayoutSpec`;
- `WorkspaceCatalog`;
- the `workspaces.json` schema;
- the R4 `mcf-bindings.json` schema.

## 4. Checkpoint resolution

R5 uses this precedence:

1. when runtime state is available, a valid `continuityCheckpointRef` from the current mission contract;
2. when runtime is unavailable, local canonical candidates under `.mcf/continuity/*.json` for the configured/bound mission id;
3. if local candidates are ambiguous at the newest valid `repositoryState.capturedAt`, no candidate is guessed and continuity is treated as unresolved.

A runtime checkpoint reference must provide:

- `artifactType = MCF_CHECKPOINT`;
- `schemaVersion = 1.1`;
- matching project identity;
- a path contained by the project root;
- a readable checkpoint JSON object.

If a runtime checkpoint reference contains `contentDigest`, the digest must match before the checkpoint is accepted.

R5 never deletes, repairs, rewrites or normalizes canonical checkpoint files.

## 5. Canonical JSON digest convention

Digest verification uses SHA-256 over UTF-8 canonical JSON:

- object keys recursively sorted;
- array order preserved;
- compact JSON separators;
- no ASCII-only coercion.

The returned form is:

`sha256:<64 lowercase hex characters>`

The MCF v1.1 checkpoint object has no root `contentDigest` field, so a checkpoint referenced by a runtime artifact ref is hashed as the entire checkpoint JSON object.

## 6. Authoritative project records

`authoritative_records_resolved` is conservative. It requires:

- repository recognized as an MCF project;
- canonical project identity resolved without consistency errors;
- checkpoint project id equal to canonical project id;
- checkpoint mission id equal to the configured/bound mission id;
- current PIP projection `VALID`;
- current PRR projection `VALID`;
- current intent-alignment projection `VALID` with decision `PASS`;
- PIP, PRR and alignment project identities equal to the checkpoint project id.

When checkpoint `alignedPipRef` or `projectRealityReportRef` is present, R5 additionally requires the ref to match the selected canonical artifact by:

- artifact type;
- schema version;
- project id;
- revision id;
- safe canonical path.

When such an artifact ref carries `contentDigest`, R5 reads that referenced canonical JSON and verifies its canonical digest. Digest mismatch makes authoritative records unresolved and therefore prevents `FAST_RESUME` or `RECONCILE`.

## 7. Methodology pin

`methodology_pin_valid` requires checkpoint methodology version and immutable ref to match both currently selected valid PIP and PRR methodology pins.

Missing or conflicting methodology evidence routes conservatively to recovery.

## 8. Read-only Git evidence

`McfGitObserver` executes only these query families, always through `subprocess.run(..., shell=False, check=False)`:

```text
git -C <root> config --get remote.origin.url
git -C <root> rev-parse --abbrev-ref HEAD
git -C <root> rev-parse HEAD
git -C <root> status --porcelain
git -C <root> cat-file -e <checkpointSha>^{commit}
git -C <root> merge-base --is-ancestor <checkpointSha> <liveSha>
git -C <root> merge-base --is-ancestor <liveSha> <checkpointSha>
```

Common GitHub HTTPS/SSH remotes are normalized to the MCF repository identity form `owner/repository`.

R5 does not execute Git mutation or synchronization commands. In particular it does not run checkout, switch, reset, merge, rebase, stash, commit, add, clean, pull, push, fetch, branch or tag.

## 9. Explainable drift

R5 labels drift explainable only when all required authority/integrity checks pass, repository identity matches and the worktree is clean.

The only explainable relationships are:

- same SHA, different branch -> `EXPLAINABLE_BRANCH_DRIFT`;
- checkpoint SHA is an ancestor of live HEAD -> `EXPLAINABLE_FORWARD_DRIFT`;
- live HEAD is an ancestor of checkpoint SHA -> `EXPLAINABLE_BACKWARD_DRIFT`.

A dirty worktree is `WORKTREE_DIRTY` and is not explainable.

Unavailable checkpoint commit evidence is `CHECKPOINT_COMMIT_UNAVAILABLE` and is not explainable.

Clean divergent histories are `UNEXPLAINED_DIVERGENCE`.

R5 never uses conversation transcript, assistant memory or unstored chat state as continuity evidence.

## 10. Stable reason vocabulary

R5 may project reason codes including:

- `MISSION_ID_ABSENT`
- `CHECKPOINT_ABSENT`
- `CHECKPOINT_AMBIGUOUS`
- `CHECKPOINT_REF_INVALID`
- `CHECKPOINT_DIGEST_MISMATCH`
- `CHECKPOINT_INTEGRITY_INVALID`
- `CHECKPOINT_NOT_TRANSFERABLE`
- `CHECKPOINT_SHA_ABSENT`
- `CHECKPOINT_COMMIT_UNAVAILABLE`
- `UNSAFE_CHECKPOINT_PATH`
- `PROJECT_ID_MISMATCH`
- `MISSION_ID_MISMATCH`
- `AUTHORITATIVE_RECORDS_UNRESOLVED`
- `METHODOLOGY_PIN_MISMATCH`
- `LIVE_GIT_UNAVAILABLE`
- `REPOSITORY_IDENTITY_MISMATCH`
- `WORKTREE_DIRTY`
- `EXACT_LIVE_MATCH`
- `EXPLAINABLE_FORWARD_DRIFT`
- `EXPLAINABLE_BACKWARD_DRIFT`
- `EXPLAINABLE_BRANCH_DRIFT`
- `UNEXPLAINED_DIVERGENCE`

Reason aggregation preserves evidence order so a concrete local cause such as `WORKTREE_DIRTY` remains primary and the pure route consequence such as `UNEXPLAINED_DIVERGENCE` can appear after it.

## 11. Cockpit projection

The `CONTINUITY` card shows only derived fields:

- `ROUTE`
- `REASON`
- `CHECKPOINT` — shortened SHA or `AUSENTE`
- `LIVE` — shortened SHA or `INDISPONÍVEL`
- `DRIFT`
- `TRANSFERABILITY`
- `NEXT ACTION` — canonical checkpoint orientation text when available
- `AUTHORITY` — `ORIENTATION_ONLY_CANONICAL_CHECKPOINT_WINS`

The existing Project, Mission, Authority and Timeline projections remain read-only.

There are no buttons that execute `FAST_RESUME`, `RECONCILE` or `RECOVER_MCF_PROJECT`.

R4's `Vincular workspace` / `Desvincular workspace` controls remain TriView-only binding metadata mutations; they do not mutate MCF state.

## 12. Forbidden R5 actions

R5 does not:

- execute any continuity route;
- create, execute, cancel or mutate a mission;
- approve or reject a HUMAN_GATE;
- grant or revoke a Standing Authorization;
- write, rewrite, remove or repair `.mcf` artifacts;
- mutate Git refs, index, worktree, branches or history;
- synchronize Git remotes;
- persist `TRIVIEW_MCF_SESSION_TOKEN` or Authorization headers;
- copy PIP, PRR, mission state, gate state, checkpoint state or authority into TriView workspace schemas;
- treat chat transcript or assistant memory as canonical evidence.

## 13. TDD and CI evidence

### Task 1 — pure decision

- RED commit `1614a44` / CI `32008944232`: module absent as expected.
- GREEN commit `e3134c5` / CI `32009103542`: full pipeline PASS.

### Task 2 — checkpoint and canonical evidence

- RED commit `f410bf4` / CI `32009213570`: checkpoint inspector absent as expected.
- GREEN commit `f04906a` / CI `32009370983`: full pipeline PASS.

### Task 3 — read-only Git and drift

- RED commit `3cb4ff6` / CI `32009484383`: Git observer absent as expected.
- GREEN commit `5148ba5` / CI `32009662411`: full pipeline PASS.

### Task 4 — analyzer and Cockpit projection

- RED HEAD `f023d1f` / CI `32009814434`: analyzer/decision interfaces absent as expected.
- GREEN implementation HEAD `5e725c1` / CI `32010170548`: full pipeline PASS.

### Review correction — canonical artifact ref digests

- RED commit `88acc5a` / CI `32010382213`: exactly one new digest test failed; 363 tests passed and 2 were skipped.
- GREEN commit `7d4c2da` / CI `32010576334`: full pipeline PASS after artifact-ref path/schema/digest validation.

Every GREEN run above passed the repository's compile, shell validation, pytest, X11 wheel integration, XTEST device integration and Xephyr containment gates.

## 14. Scope audit before final documentation commit

Exact comparison:

```text
base = 4b92086874d51ff9470ac978b12a213419d69f7a
head = 7d4c2da7abc4fb3e2ffb5df73c1848e903fd98ce
```

Result before this document:

- status: ahead;
- 15 commits ahead;
- 0 commits behind;
- production changes only in `mcf_continuity.py` and `mcf_cockpit.py`;
- remaining changes limited to R5 tests, design spec and implementation plan.

A fresh CI on the documentation HEAD is required before R5 can be reported as complete.

## 15. Completion condition

R5 may be reported as delivered only after:

1. fresh CI succeeds on the documentation HEAD;
2. final diff remains inside the boundary documented above;
3. PR #72 remains open, draft and not merged;
4. no merge occurs without a later explicit HUMAN_GATE from LEANDRO.
