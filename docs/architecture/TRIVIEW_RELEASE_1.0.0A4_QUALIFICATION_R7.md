# TriView 1.0.0a4 — R7 Qualification Evidence

## Status

`R7_TASKS_1_4_COMPLETE_PENDING_EVIDENCE_HEAD_CI`

This document is an evidence ledger for qualification of the integrated TriView train. It does not authorize promotion or publication.

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

The product candidate SHA is the immutable code/version/test identity for physical qualification. Evidence-only documentation commits may advance the branch head without changing the product candidate. The commit SHA containing this document is intentionally not embedded into the document itself because a file cannot stably contain the hash of its own commit. Any change to production code, package version, release-identity tests, lifecycle scripts, or MCF integration code invalidates the product candidate and requires a new product candidate SHA plus requalification.

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
| Physical Linux Mint/X11 | NOT_RUN | Must run on the exact product candidate SHA. |
| LEA-197 10-run matrix | NOT_RUN | Five `x-terminal-emulator` cycles + five Xed cycles required. |
| MCF integration smoke | NOT_RUN | Mission Cockpit, read-only detection, binding references, token non-persistence and continuity orientation must be checked physically. |
| Update qualification | NOT_RUN | Existing update mechanism must be exercised against the immutable candidate. |
| Rollback qualification | NOT_RUN | Existing stable rollback must pass dry-run and controlled restore cycle. |
| Blocker audit | BLOCKED | Issue #26 remains release-blocking until exact-SHA LEA-197 physical evidence passes and is recorded. |
| Final HUMAN_GATE | BLOCKED | Requires all preceding release gates PASS and explicit authorization from LEANDRO. |
| Promotion / publication | BLOCKED | No merge to `main`, tag or GitHub Release is authorized by Tasks 1–4. |

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

## Physical Linux Mint/X11 gate

State: `NOT_RUN`

The physical gate must be tied to:

`a8fd3209d6315cc7cc1870220b6c79e7296b45b3`

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

## Update and rollback

Update qualification: `NOT_RUN`

Rollback qualification: `NOT_RUN`

R7 must use the existing lifecycle mechanisms. It must not introduce a parallel updater or rollback path.

## Blockers and release boundary

- Issue #26 remains `BLOCKED` for release until the LEA-197 physical matrix passes on the exact product candidate SHA.
- Issue #68 remains V2-only and is outside this release.
- Issue #32 is not part of the `1.0.0a4` alpha qualification unless a new explicit governance decision changes its blocking status.
- `main` remains at the pre-promotion SHA until a later explicit HUMAN_GATE.
- The publication workflow must not be triggered by Tasks 1–4.

## Next authorized scope

After this evidence-head receives its own full CI PASS, the next possible work is the physical qualification and lifecycle qualification defined by R7 Tasks 5–8. Those tasks do not authorize merge into `main` or publication.
