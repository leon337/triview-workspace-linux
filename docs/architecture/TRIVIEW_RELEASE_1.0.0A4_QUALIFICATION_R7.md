# TriView 1.0.0a4 — R7 Qualification Evidence

## Status

`R7_TASKS_5_8_PREPARED_PHYSICAL_PENDING_UPDATE_BLOCKED`

This document is the canonical evidence ledger for qualification of the integrated TriView train. It does not authorize promotion or publication.

## Candidate identity

- release candidate: `1.0.0a4`
- candidate branch: `release/1.0.0a4`
- product candidate SHA: `a8fd3209d6315cc7cc1870220b6c79e7296b45b3`
- product candidate tree: `8f90aa9bfabde12bf357caaa397907526135fab9`
- source train SHA: `6d77a269f2f35474b6df922e010b1c55d658d77d`
- pre-promotion main SHA: `60b7e86dc738e1dc285e942951c67e41ac82b018`
- MCF baseline SHA: `5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`
- previous public release: `v1.0.0a3` -> `60b7e86dc738e1dc285e942951c67e41ac82b018`
- promotion PR: `#74`
- physical acceptance runbook: `docs/work/R7_1.0.0A4_PHYSICAL_ACCEPTANCE.md`

The product candidate SHA is the immutable code/version/test identity for physical qualification. Evidence-only documentation commits may advance the branch head without changing the product candidate. The commit SHA containing this document is intentionally not embedded into the document itself because a file cannot stably contain the hash of its own commit.

Any change to production code, package version, release-identity tests, lifecycle scripts, or MCF integration code invalidates the product candidate and requires a new product candidate SHA plus requalification.

## Gate state vocabulary

Only these states are used:

- `PASS`
- `FAIL`
- `BLOCKED`
- `NOT_RUN`

## Qualification gates

| Gate | State | Evidence / condition |
| --- | --- | --- |
| Freeze gate | PASS | train, main, MCF and latest public release matched the approved R7 baselines before candidate creation. |
| Release identity TDD | PASS | RED `faca655db3601c4d86cc6ba81b3c154a701f4f79`; corrected identity plus legacy documentation contract; final product candidate `a8fd3209d6315cc7cc1870220b6c79e7296b45b3`. |
| Remote CI — product candidate | PASS | GitHub Actions run `32018387686`; compile, shell validation, pytest, X11 wheel, XTEST and Xephyr all passed. |
| Remote CI — initial evidence head | PASS | GitHub Actions run `32018584616`; full matrix passed on docs-only evidence head `c79cca3d40389a2a731bfa1c6287d8b999eeda27`. |
| Physical acceptance package | PASS | Fail-closed runbook prepared at `docs/work/R7_1.0.0A4_PHYSICAL_ACCEPTANCE.md`, pinned to the product candidate SHA. |
| Remote CI — runbook/lifecycle evidence | PASS | GitHub Actions run `32020364862`; full matrix passed on docs-only evidence head `1bb7cdbd103995700e2e13ff672c382fac989f5f`. |
| Physical Linux Mint/X11 | NOT_RUN | Must run on exact product candidate `a8fd3209d6315cc7cc1870220b6c79e7296b45b3`. |
| LEA-197 10-run matrix | NOT_RUN | Five `x-terminal-emulator` cycles + five Xed cycles required. |
| MCF integration smoke | NOT_RUN | Mission Cockpit, read-only detection, binding references, token non-persistence and continuity orientation must be checked physically. |
| Remote lifecycle regression audit | PASS | Candidate includes passing regression suites for stable update safety and stable rollback/dry-run/data preservation; product candidate CI passed them. |
| Stable rollback dry-run on installed Mint | NOT_RUN | Must be executed against the actual stable installation with current/catalog fingerprints recorded. |
| Controlled stable rollback on installed Mint | NOT_RUN | Must be executed only after recording stable path/version/catalog and preserving user data. |
| Pre-publication update qualification to `1.0.0a4` | BLOCKED | Stable channel can only consume the already-published latest release (`v1.0.0a3` today); testing channel is disabled and its manifest version grammar rejects PEP 440 alpha `1.0.0a4`. No forced workaround is permitted. |
| Blocker audit | BLOCKED | Issue #26 remains release-blocking until exact-SHA LEA-197 physical evidence passes. The pre-publication updater alpha-version incompatibility must also be remediated or explicitly resolved through a separately reviewed qualification path. |
| Final HUMAN_GATE | BLOCKED | Requires all required release gates PASS, no unresolved release blocker, exact-head CI GREEN and explicit authorization from LEANDRO. |
| Promotion / publication | BLOCKED | No merge to `main`, tag or GitHub Release is authorized by the current R7 state. |

## Freeze evidence

The R7 preflight verified:

```text
TriView train = 6d77a269f2f35474b6df922e010b1c55d658d77d
TriView main  = 60b7e86dc738e1dc285e942951c67e41ac82b018
MCF main      = 5d79f488407c77f7b9f21ecfefb41ddfb3a52aef
latest release = v1.0.0a3 -> 60b7e86dc738e1dc285e942951c67e41ac82b018
```

`main` is the merge base of the frozen train. The release branch was created from the exact train SHA rather than a floating ref.

## Release identity delta

Compared with the frozen train, the product candidate changes only:

- `pyproject.toml` — `1.0.0a3` -> `1.0.0a4`;
- `README.md` — candidate release identity and concise MCF integration status;
- `CHANGELOG.md` — `1.0.0a4` candidate section;
- `tests/test_release_identity.py` — release identity contract;
- `tests/test_documentation.py` — existing release-documentation contract aligned to the new release identity without removing packaging, updater or entrypoint assertions.

No production module, updater script, rollback script, publication workflow or MCF integration implementation changed in this release-identity delta.

## TDD evidence

### RED

Commit:

`faca655db3601c4d86cc6ba81b3c154a701f4f79`

CI:

`32018020264` — `failure`

Observed pytest result:

- 369 tests collected;
- 3 failures, all in `tests/test_release_identity.py`;
- package version still `1.0.0a3`;
- README still identified `1.0.0a3`;
- CHANGELOG had no `1.0.0a4` section;
- all other tests passed, with the two dedicated X11 tests skipped in the normal pytest stage as expected.

### First GREEN attempt — legacy contract exposed

Commit:

`ee71185191f82cf4fe9eb5d94064f64945de6f1c`

CI:

`32018245559` — `failure`

The new identity contract passed, but two historical assertions in `tests/test_documentation.py` still hard-coded `1.0.0a3`. This was classified as a release-version contract gap, not a product regression.

### Final product candidate GREEN

Commit:

`a8fd3209d6315cc7cc1870220b6c79e7296b45b3`

CI:

`32018387686` — `success`

Passed stages:

```text
Install
Install X11 integration dependencies
Compile
Validate shell scripts
Tests
X11 wheel integration
XTEST device integration
Xephyr containment integration
Upload test report
```

This run is the remote-CI qualification evidence for the product candidate before physical testing.

### Initial evidence-head GREEN

Commit:

`c79cca3d40389a2a731bfa1c6287d8b999eeda27`

CI:

`32018584616` — `success`

The evidence document itself was added docs-only and the full matrix passed again.

### Physical runbook / lifecycle evidence GREEN

Evidence head before this ledger-only update:

`1bb7cdbd103995700e2e13ff672c382fac989f5f`

CI:

`32020364862` — `success`

All workflow stages passed, including compile, shell validation, pytest, X11 wheel, XTEST and Xephyr.

The diff from product candidate `a8fd3209d6315cc7cc1870220b6c79e7296b45b3` through that evidence head contains only two Markdown files:

- `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`
- `docs/work/R7_1.0.0A4_PHYSICAL_ACCEPTANCE.md`

No production code, lifecycle script, package version, release contract test or MCF integration implementation changed after the product candidate was frozen.

## Physical Linux Mint/X11 gate

State: `NOT_RUN`

The physical gate must be tied to:

`a8fd3209d6315cc7cc1870220b6c79e7296b45b3`

The executable procedure is:

`docs/work/R7_1.0.0A4_PHYSICAL_ACCEPTANCE.md`

It uses an isolated detached worktree, verifies the immutable candidate SHA through `candidate-release.json`, fingerprints the stable installation/catalog before testing, and stops on unexpected mutation or any critical failure.

Required LEA-197 matrix:

```text
T1 NOT_RUN
T2 NOT_RUN
T3 NOT_RUN
T4 NOT_RUN
T5 NOT_RUN

X1 NOT_RUN
X2 NOT_RUN
X3 NOT_RUN
X4 NOT_RUN
X5 NOT_RUN
```

Required invariants:

```text
cross-window capture = NOT_RUN
ATIVO only when embedded = NOT_RUN
EXTERNO only when actually external = NOT_RUN
resize/reopen deterministic = NOT_RUN
stable installation preserved = NOT_RUN
catalog preserved = NOT_RUN
```

Issue #26 must remain open until this exact-SHA matrix passes and the evidence is recorded.

## MCF integration physical smoke

State: `NOT_RUN`

Required checks:

```text
MCF action opens Mission Cockpit = NOT_RUN
canonical project detection remains read-only = NOT_RUN
project-workspace binding persists references only = NOT_RUN
MCF token/Authorization is not persisted = NOT_RUN
continuity route is displayed but not executed = NOT_RUN
no .mcf artifact is written by TriView = NOT_RUN
```

The physical runbook records a before/after aggregate digest of `.mcf` files. Equality is required for the read-only projection checks. It also inspects the TriView-local binding sidecar for forbidden credential-key names without printing secret values.

## Lifecycle qualification

### Remote regression audit — PASS

The product candidate contains and has already passed remote regression coverage for the existing lifecycle mechanisms.

`tests/test_stable_rollback.py` verifies, in isolated temporary roots:

- restore from a validated controlled backup;
- preservation of current workspace catalog data;
- creation of a pre-rollback code/catalog backup;
- committed transaction evidence;
- report policy `preserve-current-user-data`;
- atomic `current` switch;
- reversible rollback cycle;
- rejection of backups outside the controlled root;
- `--dry-run` validation without changing `current`, VERSION, ACTIVE-CANDIDATE, catalog, reports or transactions.

`tests/test_stable_update_safety.py` verifies, in isolated temporary roots:

- update refusal while the application lock is held;
- recording of an immutable stable tag SHA in metadata;
- preservation of active new code/controllers with explicit unresolved provenance when tag lookup fails.

The passing CI run for the product candidate is `32018387686`.

This remote audit does not replace execution against the actual installed stable copy on Linux Mint.

### Isolated product-candidate installation — supported

`scripts/install-train-candidate.sh` requires a complete immutable SHA and delegates to the candidate installer. The candidate installer uses isolated application, data and state roots under the candidate namespace, validates the source snapshot, compiles it, runs diagnostics and records `resolved_sha` in `candidate-release.json` before activation.

This enables Task 5 physical product testing without replacing the stable installation.

### Stable rollback dry-run — NOT_RUN on physical machine

The physical runbook requires:

1. stable `current`, VERSION and catalog SHA capture;
2. `triview-workspace-rollback --dry-run`;
3. exact re-check of stable `current` and catalog SHA.

The gate is not PASS until these checks are performed on the real Linux Mint installation.

### Controlled stable rollback — NOT_RUN on physical machine

A real rollback changes the active stable symlink and is intentionally separated from the non-mutating dry-run. It remains pending physical lifecycle qualification.

### Pre-publication update to `1.0.0a4` — BLOCKED

A release-blocking incompatibility was discovered during the R7 lifecycle audit.

At the exact product candidate:

1. the `stable` updater obtains the latest already-published GitHub Release; before promotion that is still `v1.0.0a3`, so `--stable` cannot activate `1.0.0a4` pre-publication;
2. the `testing` path requires an enabled testing manifest;
3. the version validator in `scripts/update-core.sh` accepts `MAJOR.MINOR.PATCH` with optional `-...` or `+...` suffix, but it does not accept the PEP 440 alpha form `1.0.0a4`;
4. `config/update-channels/testing.json` is intentionally disabled and archived.

Consequently there is no current official updater path that can activate this exact `1.0.0a4` candidate before publication while preserving the approved release ordering.

R7 does not authorize a forced manifest, a false version, publication-before-qualification, or an unreviewed change to lifecycle scripts. The update gate stays `BLOCKED` until either:

- a separate reviewed remediation makes the official pre-publication candidate path accept the release version safely; or
- a separately approved qualification design provides an equivalent, auditable supported path without weakening release governance.

Any remediation that changes lifecycle production code invalidates the current product candidate and requires a new product candidate SHA plus remote and physical requalification as applicable.

## Blockers and release boundary

Current blockers:

- Issue #26 — open until exact-SHA LEA-197 physical acceptance passes.
- Pre-publication updater alpha-version incompatibility — update qualification cannot be completed on `1.0.0a4` through the current official updater path.

Non-blocking/out-of-scope under the approved R7 design:

- Issue #68 remains V2-only and is outside this release.
- Issue #32 is not part of the `1.0.0a4` alpha qualification unless a new explicit governance decision changes its blocking status.

Release boundary:

- `main` remains at the pre-promotion SHA until a later explicit HUMAN_GATE;
- PR #74 remains draft while required gates are incomplete;
- no tag or GitHub Release may be created;
- no `.mcf` mutation, MCF recovery execution or V2 implementation is authorized by R7 qualification.

## Task 5–8 execution state

### Task 5 — Physical Linux Mint/X11

Preparation: `PASS`

Execution: `NOT_RUN`

Runbook:

`docs/work/R7_1.0.0A4_PHYSICAL_ACCEPTANCE.md`

### Task 6 — Update and rollback safety

Remote regression audit: `PASS`

Stable rollback dry-run on Mint: `NOT_RUN`

Controlled stable rollback on Mint: `NOT_RUN`

Pre-publication update to `1.0.0a4`: `BLOCKED`

### Task 7 — Blocker audit and release history

State: `BLOCKED`

Do not close issue #26 or declare blocker-free status until Task 5 passes. Do not complete release history qualification while the update gate is blocked.

### Task 8 — Final HUMAN_GATE preparation

State: `BLOCKED`

PR #74 must remain draft. It may become ready only after all required evidence is complete, blocker audit passes and exact-head CI is GREEN.

## Next authorized boundary

Physical Task 5 may proceed using the runbook and exact product candidate `a8fd3209d6315cc7cc1870220b6c79e7296b45b3`.

Task 6 may proceed only through its non-mutating/controlled physical rollback portions already defined in the runbook. The pre-publication update portion is blocked pending a separately reviewed remediation or alternative qualification decision.

No current authorization extends to changing `scripts/update-core.sh`, enabling a testing manifest, modifying version grammar, merging PR #74, promoting to `main`, creating `v1.0.0a4` or publishing a GitHub Release.
