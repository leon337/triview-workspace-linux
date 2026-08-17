# TriView R7 Qualification & Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Qualify the exact integrated train as TriView `1.0.0a4`, prove it on CI and physical Linux Mint/X11, prove update/rollback safety, close release blockers, and prepare—but not execute without a later HUMAN_GATE—the promotion to `main`.

**Architecture:** R7 is a release-qualification pipeline rather than a feature implementation. It freezes an exact train SHA, creates a release-only branch with a new version identity, gathers remote and physical evidence against one immutable candidate, and fails closed on any drift or blocker. The existing updater, rollback and publication workflows remain authoritative; R7 must not create parallel lifecycle machinery.

**Tech Stack:** Python 3.11, pytest, Bash, Git/GitHub, GitHub Actions, Linux Mint/X11, Xephyr, XTEST, xdotool, xwininfo.

## Global Constraints

- Frozen train baseline: `6d77a269f2f35474b6df922e010b1c55d658d77d`.
- Frozen TriView main baseline: `60b7e86dc738e1dc285e942951c67e41ac82b018`.
- Frozen MCF baseline: `5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`.
- Candidate version: `1.0.0a4`.
- Candidate branch: `release/1.0.0a4`.
- No feature work is allowed on the release branch.
- No merge into `main` is authorized by this plan.
- No publication is authorized by this plan.
- Any candidate code change resets the candidate SHA and invalidates affected evidence.
- Issue #68 remains V2-only and must not be implemented.
- Issue #32 is not part of this alpha qualification unless a new explicit decision changes its blocking status.
- Issue #26 is release-blocking until exact-SHA physical evidence satisfies LEA-197.
- MCF integration remains read-only/orientation-only at the boundaries established by R2-R5.

---

## File Structure

Files intentionally created or changed during R7 execution:

- Modify: `pyproject.toml` — authoritative package/release version changes from `1.0.0a3` to `1.0.0a4`.
- Modify: `README.md` — release-status identity and concise MCF integration status.
- Modify: `CHANGELOG.md` — new `1.0.0a4` release section summarizing the full promoted train delta.
- Modify: `docs/product/RELEASE_HISTORY.md` — append product-level `1.0.0a4` entry after qualification evidence exists.
- Create: `tests/test_release_identity.py` — prevents version reuse/mismatch across package and release-status docs.
- Create: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md` — canonical qualification evidence.

Files explicitly not modified unless a newly discovered release-blocking defect requires a separately reviewed remediation:

- `.github/workflows/publish-bootstrap-release.yml`
- `scripts/update.sh`
- `scripts/update-core.sh`
- `scripts/stable-rollback.sh`
- `src/triview_workspace/mcf_*.py`
- workspace domain/persistence schemas

---

### Task 1: Freeze the exact candidate lineage

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: Git refs for `train/road-to-1.0`, `main`, MCF `main`, and latest TriView release.
- Produces: an immutable preflight record containing the exact four expected identities.

- [ ] **Step 1: Re-read all release-critical refs**

Verify exactly:

```text
TriView train = 6d77a269f2f35474b6df922e010b1c55d658d77d
TriView main  = 60b7e86dc738e1dc285e942951c67e41ac82b018
MCF main      = 5d79f488407c77f7b9f21ecfefb41ddfb3a52aef
latest release = v1.0.0a3 -> 60b7e86dc738e1dc285e942951c67e41ac82b018
```

Expected: all four match. If any differs, stop R7 and return to reconciliation/qualification before creating the release branch.

- [ ] **Step 2: Verify train ancestry against main**

Run equivalent of:

```bash
git merge-base --is-ancestor 60b7e86dc738e1dc285e942951c67e41ac82b018 \
  6d77a269f2f35474b6df922e010b1c55d658d77d
```

Expected: exit `0`, with train ahead and not diverged.

- [ ] **Step 3: Create the release branch from the exact train SHA**

```bash
git branch release/1.0.0a4 6d77a269f2f35474b6df922e010b1c55d658d77d
```

When using the GitHub connector, use the exact SHA as the branch source; do not use a floating branch name.

- [ ] **Step 4: Verify the release branch head**

Expected:

```text
release/1.0.0a4 = 6d77a269f2f35474b6df922e010b1c55d658d77d
```

Do not proceed on mismatch.

---

### Task 2: Establish a unique `1.0.0a4` release identity with TDD

**Files:**
- Create: `tests/test_release_identity.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: `pyproject.toml` project version and README release-status line.
- Produces: one consistent candidate identity, `1.0.0a4`, protected by tests.

- [ ] **Step 1: Write the failing release-identity tests**

Create `tests/test_release_identity.py`:

```python
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_release_candidate_has_new_unique_version() -> None:
    assert _project_version() == "1.0.0a4"


def test_readme_release_status_matches_package_version() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "versão de liberação: `1.0.0a4`" in readme


def test_changelog_starts_with_candidate_release() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 1.0.0a4 —" in changelog
```

- [ ] **Step 2: Run the focused test and verify RED**

```bash
pytest -q tests/test_release_identity.py
```

Expected: failures because the repository still identifies itself as `1.0.0a3`.

- [ ] **Step 3: Change the package version only**

In `pyproject.toml`:

```toml
version = "1.0.0a4"
```

Do not change dependencies or build configuration.

- [ ] **Step 4: Update README release status**

Change the release-status version to `1.0.0a4` and add concise bullets stating that the candidate contains:

```text
- native read-only MCF project bridge;
- Mission Cockpit;
- project-workspace binding owned by TriView;
- continuity/reconcile orientation without executing MCF recovery routes.
```

Do not claim final physical qualification yet.

- [ ] **Step 5: Add the `1.0.0a4` changelog section**

At the top of `CHANGELOG.md`, add a section with these categories:

```markdown
## 1.0.0a4 — Integração TriView × MCF e estabilização do train

- integra o bridge MCF read-only, Mission Cockpit, binding projeto-workspace e continuidade/reconcile visual;
- preserva o MCF como fonte canônica de missão, autoridade, PIP/PRR, checkpoint e evidência;
- mantém credenciais fora da persistência TriView;
- incorpora as correções de Session Engine e Workspace Hub já qualificadas no train;
- mantém as rotas FAST_RESUME / RECONCILE / RECOVER_MCF_PROJECT apenas como orientação visual;
- não implementa o backlog V2 de isolamento multiagente.
```

Do not state that physical Mint/X11 qualification has passed until it actually has.

- [ ] **Step 6: Run the focused test and verify GREEN**

```bash
pytest -q tests/test_release_identity.py
```

Expected: PASS.

- [ ] **Step 7: Run existing publication contract tests**

```bash
pytest -q tests/test_release_publication.py
```

Expected: PASS, proving the immutable-tag and verify-before-release workflow contract was not altered.

- [ ] **Step 8: Commit the identity delta**

```bash
git add pyproject.toml README.md CHANGELOG.md tests/test_release_identity.py
git commit -m "release: prepare TriView 1.0.0a4 candidate identity"
```

Record this commit SHA as the first release-candidate head.

---

### Task 3: Open the draft promotion PR and qualify remote CI

**Files:**
- No additional product files.

**Interfaces:**
- Consumes: release branch head from Task 2.
- Produces: draft PR to `main` plus complete GitHub Actions evidence on the exact candidate SHA.

- [ ] **Step 1: Open a draft PR**

Title:

```text
Release 1.0.0a4 — qualify integrated train for stable promotion
```

Base: `main`

Head: `release/1.0.0a4`

The PR body must state:

```text
DRAFT / NOT AUTHORIZED FOR MERGE
Physical Linux Mint/X11 acceptance pending.
Update/rollback qualification pending.
Final HUMAN_GATE from LEANDRO required before promotion/publication.
```

- [ ] **Step 2: Verify the PR diff is release-prep plus the already-qualified train**

Expected: no code appears that is absent from `train/road-to-1.0`, except the release identity/docs/test delta from Task 2.

- [ ] **Step 3: Run/observe the full PR CI**

Required successful stages:

```text
Install
Compile
Validate shell scripts
Tests
X11 wheel integration
XTEST device integration
Xephyr containment integration
Upload test report
```

- [ ] **Step 4: Freeze the GREEN candidate SHA**

Record the exact PR head and workflow run ID in the qualification document draft. Any subsequent code change invalidates this record.

---

### Task 4: Create the canonical R7 qualification evidence document

**Files:**
- Create: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`

**Interfaces:**
- Consumes: preflight identities and CI evidence.
- Produces: canonical R7 evidence record progressively completed by Tasks 5-8.

- [ ] **Step 1: Create the document with immutable identity fields**

The file must begin with:

```markdown
# TriView 1.0.0a4 — R7 Qualification Evidence

## Candidate identity

- release candidate: `1.0.0a4`
- candidate branch: `release/1.0.0a4`
- candidate SHA: `<exact SHA recorded from Task 3>`
- source train SHA: `6d77a269f2f35474b6df922e010b1c55d658d77d`
- pre-promotion main SHA: `60b7e86dc738e1dc285e942951c67e41ac82b018`
- MCF baseline SHA: `5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`
```

Replace `<exact SHA recorded from Task 3>` with the actual 40-character SHA before committing; never leave the placeholder in the repository.

- [ ] **Step 2: Add gate tables with explicit states**

Use only these states:

```text
PASS
FAIL
BLOCKED
NOT_RUN
```

Required sections:

```text
Remote CI
Physical Linux Mint/X11
LEA-197 10-run matrix
MCF integration smoke
Update qualification
Rollback qualification
Blocker audit
Final HUMAN_GATE
Promotion/publication
```

- [ ] **Step 3: Commit the evidence skeleton only after replacing every placeholder**

```bash
git add docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md
git commit -m "docs: start R7 qualification evidence"
```

Because this commit changes candidate SHA, re-run full CI and update the candidate identity to the new exact SHA before physical testing. The physical-test SHA is the one that matters from this point forward.

---

### Task 5: Execute physical Linux Mint/X11 acceptance

**Files:**
- Modify: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`
- Later modify: `docs/work/LEA-197.md` only after PASS.

**Interfaces:**
- Consumes: exact final candidate SHA from Task 4 after CI GREEN.
- Produces: physical acceptance evidence tied to that SHA.

- [ ] **Step 1: Establish the physical-test preconditions**

On the Linux Mint/X11 machine:

```bash
printf 'session=%s\n' "$XDG_SESSION_TYPE"
command -v xdotool
command -v xwininfo
command -v Xephyr
command -v xauth
```

Expected: X11 session and all commands present.

- [ ] **Step 2: Install/run the exact candidate SHA through the candidate path**

Use the existing train/candidate installer with an immutable ref:

```bash
TRIVIEW_CANDIDATE_REF=<exact-candidate-sha> bash scripts/install-train-candidate.sh
```

Replace `<exact-candidate-sha>` with the actual SHA from the evidence document before executing.

- [ ] **Step 3: Run the LEA-197 terminal matrix**

Perform 5 consecutive cycles of open -> embedded-state verification -> resize/maximize -> close -> reopen for `x-terminal-emulator`.

Record each run as:

```text
T1 PASS|FAIL
T2 PASS|FAIL
T3 PASS|FAIL
T4 PASS|FAIL
T5 PASS|FAIL
```

Any FAIL blocks R7.

- [ ] **Step 4: Run the LEA-197 Xed matrix**

Perform the same 5-cycle procedure for Xed and record:

```text
X1 PASS|FAIL
X2 PASS|FAIL
X3 PASS|FAIL
X4 PASS|FAIL
X5 PASS|FAIL
```

Any FAIL blocks R7.

- [ ] **Step 5: Verify LEA-197 invariants**

Record explicit PASS/FAIL for:

```text
cross-window capture = 0
ATIVO only when embedded
EXTERNO only when actually external
resize/reopen deterministic
stable installation preserved
catalog preserved
```

- [ ] **Step 6: Run whole-product smoke acceptance**

Record PASS/FAIL individually for:

```text
Browser Xephyr no external flash
Browser wheel
Browser keyboard
same-execution workspace continuity
Workspace Hub actions visible at 1366x768
Workspace Hub created workspace activates
clean shutdown
three-gpt workspace loads
MCF action opens Mission Cockpit
MCF project detection read-only
MCF workspace binding persists references only
MCF token not persisted
continuity route shown but not executed
diagnostic package generated and sanitized
```

- [ ] **Step 7: Update the R7 evidence document with the physical matrix**

Do not summarize a partial run as PASS. Every required line must be recorded.

- [ ] **Step 8: If and only if all LEA-197 checks pass, update `docs/work/LEA-197.md`**

Change its status to a physically accepted state and include the exact candidate SHA and the 10 PASS entries. Do not close issue #26 yet; closure belongs to blocker audit after update/rollback qualification.

- [ ] **Step 9: Commit physical evidence and re-run CI**

```bash
git add docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md docs/work/LEA-197.md
git commit -m "docs: record 1.0.0a4 physical qualification"
```

This docs-only SHA becomes the new final candidate head. Re-run CI and confirm the product-code tree is unchanged from the physically tested parent except documentation.

---

### Task 6: Prove update and rollback safety

**Files:**
- Modify: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`

**Interfaces:**
- Consumes: exact candidate and existing lifecycle scripts.
- Produces: audit evidence that candidate installation and stable rollback preserve user state.

- [ ] **Step 1: Capture stable pre-test state**

Record:

```bash
readlink -f ~/.local/share/triview-workspace/current
cat ~/.local/share/triview-workspace/VERSION 2>/dev/null || true
sha256sum "${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace/workspaces.json"
```

- [ ] **Step 2: Validate rollback without mutation**

```bash
triview-workspace-rollback --dry-run
```

Expected: PASS with no active-release switch and no catalog modification.

- [ ] **Step 3: Activate/test the exact candidate through the supported candidate/update path**

Confirm the candidate validates before activation and creates the expected backup/provenance records.

- [ ] **Step 4: Run diagnostic on the candidate**

```bash
triview-workspace-diagnose
```

Expected: sanitized diagnostic package generated successfully.

- [ ] **Step 5: Execute one controlled rollback to the previous stable release**

```bash
triview-workspace-rollback
```

Expected: previous stable release becomes active after validation.

- [ ] **Step 6: Verify stable launch and data preservation after rollback**

```bash
readlink -f ~/.local/share/triview-workspace/current
sha256sum "${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace/workspaces.json"
```

Expected: release pointer is restored appropriately and the workspace catalog hash matches the intended preserved data state.

- [ ] **Step 7: Record rollback evidence**

Add exact paths/IDs of the rollback report and backup provenance to the R7 qualification document. Do not include secrets or raw browser/session credentials.

---

### Task 7: Complete blocker audit and release history

**Files:**
- Modify: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`
- Modify: `docs/product/RELEASE_HISTORY.md`
- Potential issue metadata change: close GitHub issue #26 only after evidence is complete.

**Interfaces:**
- Consumes: CI, physical, update and rollback PASS evidence.
- Produces: blocker-free release-candidate record.

- [ ] **Step 1: Re-scan open release blockers**

Required assertions:

```text
Critical = 0
High functional = 0
#68 = BACKLOG_V2, not implemented
#32 = not release-blocking for 1.0.0a4 under current R7 decision
#26 = satisfied by exact-SHA physical evidence
```

If any assertion is false, leave the PR draft and stop.

- [ ] **Step 2: Close issue #26 with exact evidence references**

The closing comment must identify:

```text
candidate SHA
5/5 terminal PASS
5/5 Xed PASS
0 cross-window capture
CI run ID
R7 evidence document path
```

Close only after all values are real and verified.

- [ ] **Step 3: Add `1.0.0a4` to product release history**

Append a product-level entry describing:

```text
MCF bridge/cockpit/binding/continuity integration
Session Engine and Workspace Hub stabilization included in train
physical Linux Mint/X11 qualification result
update/rollback qualification result
MCF source-of-truth and read-only authority boundaries
```

- [ ] **Step 4: Commit blocker/history evidence**

```bash
git add docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md docs/product/RELEASE_HISTORY.md
git commit -m "docs: complete 1.0.0a4 release qualification"
```

Run full CI again because the final HUMAN_GATE must reference the exact final PR head.

---

### Task 8: Prepare the final promotion gate without merging

**Files:**
- Modify only PR metadata/body if needed.
- No repository product changes.

**Interfaces:**
- Consumes: exact final candidate SHA with every R7 gate PASS.
- Produces: one explicit HUMAN_GATE request containing the immutable promotion target.

- [ ] **Step 1: Re-read final refs**

Verify:

```text
main remains 60b7e86dc738e1dc285e942951c67e41ac82b018
MCF remains 5d79f488407c77f7b9f21ecfefb41ddfb3a52aef
release/1.0.0a4 = <final exact candidate SHA>
```

If `main` or MCF drifted, stop and reconcile before asking for promotion.

- [ ] **Step 2: Verify final CI on exact head**

All full-CI stages must be `success`. Record the workflow run ID in the evidence document and PR body.

- [ ] **Step 3: Verify final qualification document contains no `NOT_RUN` or unresolved `BLOCKED` gate**

`FAIL` anywhere blocks promotion.

- [ ] **Step 4: Mark the draft PR ready only after all previous checks pass**

The PR body must still state that merge requires LEANDRO's explicit authorization.

- [ ] **Step 5: Request final HUMAN_GATE**

The gate request must state exactly:

```text
Authorize merge release/1.0.0a4@<final SHA> -> main@60b7e86...
and authorize the resulting publish workflow to create v1.0.0a4
only if post-merge verification remains GREEN.
```

No merge may occur until LEANDRO explicitly approves this exact target.

---

### Task 9: Promotion and publication — execute only after the future HUMAN_GATE

**Files:**
- Repository mutation: PR merge to `main`.
- Modify: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md` in a follow-up documentation PR if final merge/release evidence needs to be recorded.

**Interfaces:**
- Consumes: the exact future HUMAN_GATE authorization.
- Produces: `main` promotion and, after workflow verification, `v1.0.0a4` publication.

- [ ] **Step 1: Reconfirm authorized SHA immediately before merge**

The PR head must equal the SHA explicitly authorized by LEANDRO. Otherwise do not merge.

- [ ] **Step 2: Merge using a merge commit**

Preserve release provenance; do not squash the qualification history into an unrelated identity.

- [ ] **Step 3: Verify CI on the resulting exact `main` SHA**

Required: complete CI success.

- [ ] **Step 4: Verify the publication workflow**

Because `pyproject.toml` changed, confirm `Publish stable release` runs its `verify` job and only then creates/accepts `v1.0.0a4` at the exact `main` SHA.

- [ ] **Step 5: Verify immutable release identity**

Required:

```text
latest release = v1.0.0a4
release target SHA = exact authorized main SHA
project version = 1.0.0a4
```

- [ ] **Step 6: If post-merge verification fails, stop forward**

Do not rewrite `main` history and do not force-move a tag. Open a remediation branch and use the installed stable rollback mechanism for affected machines if needed.

---

## Self-Review

- Spec coverage: freeze/version, CI, physical Mint/X11, LEA-197, MCF smoke, update/rollback, blockers, final HUMAN_GATE and publication semantics are each assigned to a concrete task.
- Placeholder scan: placeholders appear only in executable templates that explicitly require replacement with a real SHA before repository write/execution; the plan forbids committing them unresolved.
- Type/interface consistency: candidate identity always means one exact 40-character release-branch SHA; physical evidence and final gate both bind to that identity.
- Safety boundary: no step authorizes merge or publication before Task 8 obtains a new explicit LEANDRO HUMAN_GATE.
