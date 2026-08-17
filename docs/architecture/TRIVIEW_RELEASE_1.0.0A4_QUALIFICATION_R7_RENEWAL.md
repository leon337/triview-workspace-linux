# TriView 1.0.0a4 — R7 Renewed Qualification Evidence

## Status

`R7_RENEWED_CANDIDATE_PHYSICAL_PENDING`

This document records the renewed R7 qualification state after the minimal prerelease-updater remediation. It does not authorize promotion or publication.

## Current candidate identity

- release candidate: `1.0.0a4`
- candidate branch: `release/1.0.0a4`
- **product candidate SHA:** `42b2782a3b3104d53d3ad284b7f941e63f4dab48`
- **product candidate tree:** `70559e1bee4a740025c0a31fd8d92e537981f661`
- **product candidate CI:** `32038623140` — `success`
- source train SHA: `6d77a269f2f35474b6df922e010b1c55d658d77d`
- pre-promotion main SHA: `60b7e86dc738e1dc285e942951c67e41ac82b018`
- MCF baseline SHA: `5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`
- promotion PR: `#74` — must remain draft until all required gates pass
- current physical runbook: `docs/work/R7_1.0.0A4_PHYSICAL_ACCEPTANCE_RENEWED.md`

The product candidate SHA above is the immutable code/version/test identity for renewed physical qualification. Documentation-only evidence commits may advance the branch head without changing the product candidate.

The former product candidate `a8fd3209d6315cc7cc1870220b6c79e7296b45b3` is historical only. It must not be used for new physical acceptance because lifecycle production code changed after it was frozen.

## Why the candidate was renewed

R7 lifecycle qualification discovered that the testing-manifest version grammar rejected PEP 440 alpha versions such as `1.0.0a4`. A separately reviewed minimal remediation was implemented and qualified through PR #75.

TDD evidence:

- RED commit: `c995f2b4230b427abfb085b2e4b56262fc966a72`
- RED CI: `32037661271` — expected failure
- RED shape: exactly three failures for `1.0.0a4`, `1.0.0b2`, `1.0.0rc1`; 381 tests passed and 2 were skipped
- GREEN commit: `269a32b012e8f4b34b457e5c291f8cf129c4ad55`
- GREEN CI: `32037833328` — full matrix PASS
- integration merge commit / renewed product candidate: `42b2782a3b3104d53d3ad284b7f941e63f4dab48`
- renewed exact-head CI: `32038623140` — full matrix PASS

The production delta in the remediation is one line in `scripts/update-core.sh`: the testing-manifest `version` regex now preserves the previously accepted forms and additionally accepts only lowercase simple prereleases `aN`, `bN`, and `rcN`. The accompanying test contract is in `tests/test_update_channel.py`.

No repository testing manifest was enabled, no stable-channel discovery changed, no SHA-pinning rule changed, and no dependency was added.

## Gate state

| Gate | State | Evidence / condition |
| --- | --- | --- |
| R7 freeze baseline | PASS | train/main/MCF baselines remain the approved values. |
| Release identity TDD | PASS | `1.0.0a4` identity contract already qualified. |
| Updater prerelease remediation TDD | PASS | RED `32037661271`; GREEN `32037833328`; PR #75 integrated by merge commit. |
| Remote CI — renewed product candidate | PASS | `32038623140` on exact SHA `42b2782a3b3104d53d3ad284b7f941e63f4dab48`; compile, shell, pytest, X11 wheel, XTEST and Xephyr passed. |
| Updater alpha-version grammar blocker | PASS | `1.0.0a4`, `bN` and `rcN` simple forms are now accepted by the controlled testing-manifest validator. |
| Repository testing manifest policy | PASS | `config/update-channels/testing.json` remains disabled/archived; no repository-wide testing channel was activated. |
| Physical Linux Mint/X11 | NOT_RUN | Must run on exact renewed product candidate SHA. |
| LEA-197 10-run matrix | NOT_RUN | Five terminal + five Xed cycles, zero cross-window capture. |
| MCF integration physical smoke | NOT_RUN | Mission Cockpit/read-only/binding/continuity/credential boundaries must be checked physically. |
| Pre-publication controlled testing update | NOT_RUN | Runbook uses an explicit temporary enabled manifest pinned to the renewed SHA and isolated roots; repository manifest remains disabled. |
| Stable rollback dry-run on installed Mint | NOT_RUN | Must preserve stable current and catalog fingerprints. |
| Controlled stable rollback on installed Mint | NOT_RUN | Must preserve user data and use controlled backup roots. |
| Blocker audit | BLOCKED | Issue #26 remains open until exact-SHA physical LEA-197 evidence passes. |
| Final HUMAN_GATE | BLOCKED | Requires all required gates PASS, blocker audit clear, exact-head CI GREEN and fresh LEANDRO approval. |
| Promotion / publication | BLOCKED | No merge to `main`, tag or GitHub Release is authorized. |

## Pre-publication update path after remediation

The previous grammar blocker is resolved, but this does **not** enable the repository testing channel.

The supported qualification path is deliberately explicit and local to the physical test:

1. start from `config/update-channels/testing.json` as a schema template;
2. create a temporary manifest outside the repository;
3. set `enabled=true`, `version=1.0.0a4`, and `ref=42b2782a3b3104d53d3ad284b7f941e63f4dab48`;
4. keep `candidate_id=LEA-197` and a valid module;
5. pass it through `TRIVIEW_TEST_MANIFEST_FILE`;
6. run the updater in isolated application/data/state roots;
7. first require `--dry-run` PASS, then perform the controlled isolated testing update;
8. verify installed `VERSION`, `ACTIVE-CANDIDATE.json.ref`, and stable-installation fingerprints.

This proves the pre-publication candidate path without enabling `config/update-channels/testing.json`, without lying about the version, and without publishing `v1.0.0a4` before qualification.

## Physical acceptance boundary

The current physical procedure is:

`docs/work/R7_1.0.0A4_PHYSICAL_ACCEPTANCE_RENEWED.md`

Required physical evidence remains:

```text
Linux Mint / X11 preconditions
5 x x-terminal-emulator
5 x Xed
0 wrong-window capture
ATIVO only when embedded
EXTERNO only when actually external
resize/reopen deterministic
Browser Xephyr/wheel/keyboard smoke
Workspace continuity + Hub smoke
Mission Cockpit + MCF read-only digest
binding references-only
no credential persistence
continuity orientation-only
candidate diagnostic
controlled testing update dry-run
controlled isolated testing update to 1.0.0a4
stable rollback dry-run
controlled stable rollback
stable installation/catalog preservation
```

Issue #26 remains open until the exact renewed SHA passes its required physical matrix and the evidence is recorded.

## Release boundary

- `main` must remain at `60b7e86dc738e1dc285e942951c67e41ac82b018` until a later explicit promotion HUMAN_GATE.
- PR #74 remains draft while any required gate is `NOT_RUN`, `FAIL`, or `BLOCKED`.
- No tag or GitHub Release may be created.
- No `.mcf` canonical mutation, MCF recovery execution or V2 work is authorized by this qualification.

## Supersession note

`docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md` and `docs/work/R7_1.0.0A4_PHYSICAL_ACCEPTANCE.md` preserve the pre-remediation evidence and old product-candidate pin. They are historical after PR #75 integration.

For all new R7 physical work, this renewal ledger and `R7_1.0.0A4_PHYSICAL_ACCEPTANCE_RENEWED.md` are authoritative until another production change invalidates `42b2782a3b3104d53d3ad284b7f941e63f4dab48`.
