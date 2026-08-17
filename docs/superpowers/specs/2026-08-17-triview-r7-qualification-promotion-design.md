# TriView R7 — Qualification & Promotion Design

## Status

Design approved by LEANDRO on 2026-08-17. This document defines the qualification path from the integrated development train to a release candidate. It does **not** authorize promotion to `main`, publication, deployment, or release creation.

## Mission

Qualify the entire current `train/road-to-1.0` as a coherent release candidate, assign a new immutable version identity, obtain physical Linux Mint/X11 evidence, prove update/rollback safety, eliminate release blockers, and only then request a separate HUMAN_GATE for promotion to `main`.

## Frozen baselines

At design time:

- TriView train: `6d77a269f2f35474b6df922e010b1c55d658d77d`
- TriView main: `60b7e86dc738e1dc285e942951c67e41ac82b018`
- MCF main / v1.1 baseline: `5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`
- public TriView release: `v1.0.0a3` -> `60b7e86dc738e1dc285e942951c67e41ac82b018`

The train is 84 commits ahead and 0 behind `main`. Qualification therefore covers the whole train, not only R2-R6.

Any change to the train baseline or the MCF baseline invalidates the frozen-candidate evidence until requalified.

## Release identity

The candidate version is **`1.0.0a4`**.

`1.0.0a3` cannot be reused because the public tag/release already identifies the older `main` tree. Two different product trees must never share the same release version.

A future `1.0.0` decision is explicitly outside R7. Issue #32 (Visual Evolution) may continue before final V1 branding without blocking an alpha release candidate.

## Chosen promotion architecture

```text
train/road-to-1.0 @ frozen SHA
        |
        v
release/1.0.0a4
        |
        +-- version/release-doc-only delta
        |
        +-- CI qualification
        |
        +-- physical Mint/X11 qualification
        |
        +-- update + rollback qualification
        |
        +-- blocker audit
        |
        v
FINAL HUMAN_GATE — LEANDRO
        |
        v
main
        |
        v
publication workflow -> v1.0.0a4
```

The release branch must not contain feature work. Only version identity, release documentation, qualification evidence, and changes strictly required to fix a release-blocking defect discovered during qualification are allowed. Any blocker fix resets the candidate SHA and requires the affected gates to run again.

## Gate 1 — Freeze and identity

Before creating the candidate branch:

1. verify `train/road-to-1.0` still equals the frozen SHA;
2. verify `main` still equals its baseline SHA;
3. verify MCF main still equals its baseline SHA;
4. verify the latest public TriView release remains `v1.0.0a3` at the expected SHA;
5. create `release/1.0.0a4` from the exact frozen train SHA;
6. change the project version to `1.0.0a4`;
7. add release notes describing the whole promoted delta, including MCF integration R2-R6 and the already integrated train fixes;
8. open a draft PR `release/1.0.0a4 -> main`.

No merge authorization is implied by opening the PR.

## Gate 2 — Remote CI

The exact candidate head must pass the repository's full CI:

- editable install with dev dependencies;
- compile `src` and `tests`;
- shell syntax validation;
- complete pytest suite;
- X11 wheel integration;
- XTEST device integration;
- authenticated Xephyr containment integration.

Any code change after GREEN invalidates the gate and requires a fresh run on the new SHA.

## Gate 3 — Physical Linux Mint/X11 acceptance

Physical acceptance is mandatory because CI cannot prove the full desktop/runtime behavior on the target machine.

### LEA-197 blocker acceptance

The exact release-candidate SHA must demonstrate:

- 5 consecutive open/close/reopen cycles of `x-terminal-emulator`;
- 5 consecutive open/close/reopen cycles of Xed;
- zero cross-window capture;
- deterministic classification: `ATIVO` only when embedded and `EXTERNO` only when external;
- resize/maximize/reopen behavior remains correct;
- the stable installation and user catalog remain preserved.

Issue #26 may be closed only after this evidence is recorded against the exact candidate SHA.

### Whole-product smoke acceptance

The same physical candidate must also validate:

- application starts normally on Linux Mint/X11;
- Browser Panels remain contained in authenticated Xephyr without external flash;
- keyboard and wheel input work in the intended Browser Panel;
- workspace switching preserves live same-execution sessions;
- Workspace Hub actions remain visible at 1366x768;
- creating/using a Workspace Hub workspace activates it correctly;
- Session Engine clean shutdown remains correct;
- existing three-GPT workspace still loads;
- MCF header action opens Mission Cockpit;
- MCF read-only bridge detects a valid project without writing `.mcf`;
- workspace binding persists only TriView-owned references and no credentials;
- continuity view can show `FAST_RESUME`, `RECONCILE`, or `RECOVER_MCF_PROJECT` as orientation without executing any route;
- no MCF token or Authorization header is persisted;
- diagnostic collection completes and remains sanitized.

A failure in any critical item blocks promotion.

## Gate 4 — Update and rollback

Use the existing stable lifecycle; do not create a parallel updater.

The exact candidate must be exercised through the supported candidate/update path while preserving the currently installed stable release. Required evidence:

1. candidate installation from the exact immutable SHA;
2. validation before activation;
3. preservation of workspace/catalog data;
4. diagnostic pass on the candidate;
5. stable rollback `--dry-run` pass;
6. one controlled rollback cycle to the previously stable release;
7. verification that the restored stable release launches and user data is preserved;
8. where applicable, verify the inverse path remains available through the pre-rollback backup.

No release publication is needed to execute this gate.

## Gate 5 — Blocker audit

Before requesting promotion:

- Critical blockers: 0;
- High functional blockers: 0;
- issue #26 must be closed with exact-SHA physical evidence;
- issue #68 remains `BACKLOG_V2` and must not be implemented in R7;
- issue #32 remains a post-alpha visual-evolution track unless a new explicit decision changes its release-blocking status;
- no unresolved MCF source-of-truth, credential persistence, authority-bypass, or canonical-artifact-write finding may remain.

## Gate 6 — Promotion readiness

The draft PR may become ready for final review only when all previous gates are PASS and its head SHA is frozen.

Immediately before the final HUMAN_GATE:

1. re-read `main`, candidate head, and MCF refs;
2. verify no unexpected drift;
3. verify the candidate is based on the intended train lineage and `main` has not advanced unexpectedly;
4. verify full CI GREEN on the exact candidate head;
5. attach physical acceptance and update/rollback evidence to the PR/repository docs;
6. state the exact merge SHA that will be authorized;
7. state that merging changes `pyproject.toml` to `1.0.0a4`, so the stable publication workflow will be eligible to run on `main`.

Then and only then request a new explicit HUMAN_GATE from LEANDRO.

## Publication semantics

The repository publication workflow verifies the exact `main` SHA before creating a release. Because R7 intentionally changes `pyproject.toml`, a successful authorized merge to `main` will satisfy the workflow path trigger and may lead to publication of `v1.0.0a4` after the workflow's verification stage.

Therefore the final R7 HUMAN_GATE must authorize **both** promotion to `main` and the resulting `v1.0.0a4` publication behavior. The current design approval does not grant that authorization.

## Rollback after promotion

If the post-merge CI/release verification fails, do not rewrite `main` history. Stop publication and diagnose on a new remediation branch. If a published `1.0.0a4` later proves unsafe in the field, use the existing stable rollback mechanism for installations and handle repository remediation through a new forward-fix release.

## Evidence record

R7 must eventually write a final qualification document, proposed path:

`docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`

It must contain:

- candidate SHA;
- train/main/MCF baselines;
- CI run IDs;
- physical Mint/X11 results;
- LEA-197 ten-run table;
- update/rollback evidence;
- blocker audit;
- final risk statement;
- final HUMAN_GATE decision;
- promotion merge SHA and release SHA if promotion is later authorized.

## Non-goals

R7 does not:

- implement V2 multiagent isolation;
- execute MCF resume/reconcile/recovery actions;
- add MCF write authority;
- redesign the whole UI;
- implement issue #32;
- change workspace schemas for MCF semantics;
- publish `1.0.0`;
- merge into `main` without the later explicit HUMAN_GATE.

## Decision

The candidate strategy is `release/1.0.0a4`, with promotion blocked until remote CI, physical Linux Mint/X11 acceptance, update/rollback qualification, and blocker audit all pass on the exact frozen candidate SHA.
