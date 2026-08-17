# R7 — Minimal prerelease updater remediation design

## Status

`DESIGN_APPROVED_IMPLEMENTATION_NOT_AUTHORIZED`

This specification defines the minimal remediation for the R7 pre-publication updater blocker discovered while qualifying TriView `1.0.0a4`.

It does not authorize implementation, enable the testing channel, change the release candidate, merge to `main`, create a tag, or publish a GitHub Release.

## Baseline

Design source branch:

`release/1.0.0a4`

Design source SHA:

`678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac`

Frozen pre-remediation product candidate:

`a8fd3209d6315cc7cc1870220b6c79e7296b45b3`

The existing product candidate remains the reference for the already-recorded R7 evidence, but any approved implementation that modifies `scripts/update-core.sh` invalidates it as the product candidate for final release qualification.

## Problem

The controlled testing-manifest parser in `scripts/update-core.sh` validates `version` with a SemVer-like expression:

```text
MAJOR.MINOR.PATCH
MAJOR.MINOR.PATCH-<suffix>
MAJOR.MINOR.PATCH+<suffix>
```

The R7 release identity uses PEP 440 alpha syntax:

```text
1.0.0a4
```

As a result, an otherwise valid enabled testing manifest for the exact `1.0.0a4` candidate is rejected before download or activation.

This blocks pre-publication update qualification through the official testing-manifest path.

## Goal

Preserve every version form currently accepted by the testing-manifest validator and add only these simple PEP 440 prerelease forms:

```text
MAJOR.MINOR.PATCHaN
MAJOR.MINOR.PATCHbN
MAJOR.MINOR.PATCHrcN
```

where `N` is one or more decimal digits. The prerelease markers are lowercase-only: `a`, `b`, and `rc`.

Examples that must become valid:

```text
1.0.0a4
1.0.0b2
1.0.0rc1
```

## Non-goals

The remediation must not:

- implement a general PEP 440 parser;
- add a new Python dependency;
- accept uppercase prerelease markers;
- accept epochs;
- accept `.devN` or `.postN` releases;
- accept local-version suffixes combined with the new prerelease forms;
- change stable-channel discovery;
- enable `config/update-channels/testing.json`;
- change testing-manifest schema version;
- loosen `candidate_id`, `ref`, `module`, or `status` validation;
- weaken full-SHA pinning;
- change archive selection, download, extraction, compile, activation, backup, rollback, or lifecycle locking;
- touch MCF integration behavior;
- alter `main`, tags, or public releases.

## Accepted version grammar

The validator must continue accepting the existing forms:

```text
1.0.0
1.0.0-test.1
1.0.0+build.1
```

and additionally accept:

```text
1.0.0a4
1.0.0b2
1.0.0rc1
```

The approved minimal regular-expression contract is:

```text
[0-9]+\.[0-9]+\.[0-9]+(?:a[0-9]+|b[0-9]+|rc[0-9]+|[-+][A-Za-z0-9.-]+)?
```

It preserves the existing legacy suffix grammar exactly and adds only mutually exclusive lowercase `aN`, `bN`, and `rcN` alternatives.

## Explicit rejection set

At minimum, tests must prove rejection of:

```text
1.0
v1.0.0
1.0.0a
1.0.0b
1.0.0rc
1.0.0A4
1.0.0RC1
1.0.0dev1
1.0.0.dev1
1.0.0post1
1.0.0.post1
1.0.0a4+build
1.0.0rc1+build
```

These are rejected deliberately because they are outside the approved minimal scope, not because they are universally invalid version strings.

## Implementation boundary

The production change is restricted to the `version` validation inside `read_testing_manifest()` in:

`scripts/update-core.sh`

The preferred implementation is the exact minimal extension of the existing regular expression rather than a new parser or dependency.

No other production file should change unless a failing regression proves that a second production change is strictly required. Such a finding must stop implementation and return to design review rather than expanding scope implicitly.

## Test design

Primary test file:

`tests/test_update_channel.py`

### RED contract

Before changing production code, add tests using a temporary enabled testing manifest and the existing `--testing --dry-run` path.

The RED stage must demonstrate that `1.0.0a4` is rejected by the current validator while the rest of the controlled-manifest flow remains unchanged.

### GREEN positive matrix

The completed remediation must demonstrate acceptance of:

```text
1.0.0
1.0.0-test.1
1.0.0+build.1
1.0.0a4
1.0.0b2
1.0.0rc1
```

For each newly accepted prerelease form, the dry-run must still prove:

- the manifest is explicitly enabled;
- the candidate id remains valid;
- the ref is a complete 40-hex commit SHA;
- the selected archive is pinned to that SHA;
- no activation occurs during dry-run;
- no fallback to `main` is used.

### GREEN negative matrix

The explicit rejection set in this specification must remain rejected.

Tests must assert failure at manifest validation and must not weaken the existing disabled-manifest test.

### Regression suite

After targeted tests pass, the full repository CI matrix must pass, including:

- shell syntax validation;
- normal pytest suite;
- X11 wheel integration;
- XTEST device integration;
- Xephyr containment integration.

## Branch and PR strategy

Implementation must not be committed directly to `release/1.0.0a4` during RED/GREEN development.

After written-spec approval and implementation-plan approval, create a dedicated remediation branch from the exact current release-branch head:

`fix/triview-r7-updater-prerelease-version`

The remediation PR should target `release/1.0.0a4`, not `main`.

The R7 promotion PR `#74` must remain draft while the remediation is developed and qualified.

No remediation PR merge is authorized by this design approval alone.

## Candidate invalidation and renewal

Because `scripts/update-core.sh` is lifecycle production code, merging this remediation into the release branch invalidates the frozen product candidate:

`a8fd3209d6315cc7cc1870220b6c79e7296b45b3`

After the remediation is integrated into `release/1.0.0a4`, R7 must define a new immutable product candidate SHA.

That new SHA must receive:

1. full remote CI;
2. the physical Linux Mint/X11 acceptance matrix;
3. MCF physical smoke;
4. stable rollback dry-run and controlled rollback evidence as required by R7;
5. pre-publication updater qualification through the remediated supported path.

Evidence already tied specifically to `a8fd3209…` may remain historical evidence but cannot be presented as physical qualification of the new product candidate.

## Security and governance invariants

The remediation must preserve:

- complete immutable SHA pinning for testing candidates;
- fail-closed manifest validation;
- disabled testing channel by default;
- no implicit testing activation;
- no publication-before-qualification;
- no stable-channel semantic change;
- no automatic merge;
- no tag or release creation;
- no change to MCF read-only/security boundaries.

## Success criteria

The remediation is technically qualified only when all of the following are true:

1. a test-only RED commit proves current rejection of `1.0.0a4`;
2. the production delta is limited to the approved version-validator scope;
3. the positive matrix accepts existing legacy forms plus `aN`, `bN`, and `rcN`;
4. the negative matrix rejects all explicitly out-of-scope forms;
5. disabled testing manifests still fail closed;
6. full-SHA pinning and dry-run non-activation remain intact;
7. full CI is green on the exact remediation head;
8. the remediation remains unmerged until a fresh HUMAN_GATE authorizes integration into `release/1.0.0a4`.

## Promotion boundary

Even after the remediation itself is qualified and integrated into the release branch:

- PR #74 remains draft until the renewed R7 candidate passes all remaining gates;
- no merge to `main` is implied;
- no `v1.0.0a4` tag or GitHub Release is implied;
- final promotion/publication still requires the separate R7 HUMAN_GATE.
