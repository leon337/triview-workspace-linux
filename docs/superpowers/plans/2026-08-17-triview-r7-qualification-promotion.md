# TriView R7 Qualification & Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Qualify the exact integrated train as TriView `1.0.0a4`, prove it on CI and physical Linux Mint/X11, prove update/rollback safety, close release blockers, and prepare—but not execute without a later HUMAN_GATE—the promotion to `main`.

**Architecture:** R7 is a fail-closed release-qualification pipeline, not a feature cycle. It freezes one train SHA, creates a release-only branch with a new identity, gathers all evidence against exact SHAs, and reuses the existing updater/rollback/publication machinery. Any code change invalidates affected evidence and requires requalification.

**Tech Stack:** Python 3.11, pytest, Bash, Git/GitHub, GitHub Actions, Linux Mint/X11, Xephyr, XTEST, xdotool, xwininfo.

## Global Constraints

```bash
export TRAIN_SHA=6d77a269f2f35474b6df922e010b1c55d658d77d
export MAIN_SHA=60b7e86dc738e1dc285e942951c67e41ac82b018
export MCF_SHA=5d79f488407c77f7b9f21ecfefb41ddfb3a52aef
export RELEASE_BRANCH=release/1.0.0a4
export RELEASE_VERSION=1.0.0a4
```

- No feature work is allowed on `release/1.0.0a4`.
- No merge into `main` is authorized by this plan.
- No publication is authorized by this plan.
- Issue #26 blocks promotion until exact-SHA physical LEA-197 evidence passes.
- Issue #68 remains V2-only.
- Issue #32 is outside this alpha qualification unless a later explicit decision changes its status.
- MCF integration remains read-only/orientation-only at the R2-R5 boundaries.

## File Structure

- Create: `tests/test_release_identity.py` — protects the new release identity.
- Modify: `pyproject.toml` — version only.
- Modify: `README.md` — release identity and concise MCF status.
- Modify: `CHANGELOG.md` — `1.0.0a4` technical release summary.
- Modify: `docs/product/RELEASE_HISTORY.md` — product-level release history after qualification.
- Create: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md` — canonical evidence.

Do not modify lifecycle scripts, publication workflow, MCF production modules, or workspace schemas unless a newly discovered release-blocking defect receives a separate reviewed remediation.

---

### Task 1: Freeze the exact candidate lineage

**Files:** none.

**Interfaces:**
- Consumes: live TriView/MCF refs and latest release metadata.
- Produces: one immutable release-branch starting point.

- [ ] **Step 1: Re-read all release-critical identities**

Verify exactly:

```text
train/road-to-1.0 = 6d77a269f2f35474b6df922e010b1c55d658d77d
main              = 60b7e86dc738e1dc285e942951c67e41ac82b018
MCF main          = 5d79f488407c77f7b9f21ecfefb41ddfb3a52aef
latest release    = v1.0.0a3 -> 60b7e86dc738e1dc285e942951c67e41ac82b018
```

Stop on any mismatch.

- [ ] **Step 2: Verify ancestry**

```bash
git merge-base --is-ancestor "$MAIN_SHA" "$TRAIN_SHA"
```

Expected: exit `0`; compare must show train ahead and 0 behind.

- [ ] **Step 3: Create the release branch from the exact train SHA**

```bash
git branch "$RELEASE_BRANCH" "$TRAIN_SHA"
```

With the GitHub connector, use `TRAIN_SHA` as the exact branch source, never a floating ref.

- [ ] **Step 4: Verify the branch**

```bash
test "$(git rev-parse "$RELEASE_BRANCH")" = "$TRAIN_SHA"
```

Expected: exit `0`.

---

### Task 2: Establish the `1.0.0a4` identity with TDD

**Files:**
- Create: `tests/test_release_identity.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: existing version-bearing files.
- Produces: one consistent new identity, `1.0.0a4`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_release_identity.py`:

```python
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_release_candidate_has_unique_version() -> None:
    assert project_version() == "1.0.0a4"


def test_readme_matches_release_identity() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "versão de liberação: `1.0.0a4`" in text


def test_changelog_contains_candidate_heading() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 1.0.0a4 —" in text
```

- [ ] **Step 2: Verify RED**

```bash
pytest -q tests/test_release_identity.py
```

Expected: failure because the tree still identifies itself as `1.0.0a3`.

- [ ] **Step 3: Change the package version only**

In `pyproject.toml`:

```toml
version = "1.0.0a4"
```

Do not alter dependencies/build configuration.

- [ ] **Step 4: Update README release identity**

Change `versão de liberação` to `1.0.0a4`. Add concise status bullets for the read-only MCF bridge, Mission Cockpit, project-workspace binding, and continuity/reconcile orientation. Do not claim physical PASS yet.

- [ ] **Step 5: Add the changelog heading and bounded release summary**

Use:

```markdown
## 1.0.0a4 — Integração TriView × MCF e estabilização do train

- integra bridge MCF read-only, Mission Cockpit, binding projeto-workspace e continuidade/reconcile visual;
- preserva o MCF como fonte canônica de missão, autoridade, PIP/PRR, checkpoint e evidência;
- mantém credenciais fora da persistência TriView;
- incorpora as correções qualificadas de Session Engine e Workspace Hub já presentes no train;
- mantém FAST_RESUME / RECONCILE / RECOVER_MCF_PROJECT apenas como orientação visual;
- não implementa o backlog V2 de isolamento multiagente.
```

- [ ] **Step 6: Verify GREEN and publication-contract regression**

```bash
pytest -q tests/test_release_identity.py
pytest -q tests/test_release_publication.py
```

Expected: both PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml README.md CHANGELOG.md tests/test_release_identity.py
git commit -m "release: prepare TriView 1.0.0a4 candidate identity"
export CANDIDATE_SHA="$(git rev-parse HEAD)"
```

---

### Task 3: Open the draft promotion PR and qualify remote CI

**Files:** no new product files.

**Interfaces:**
- Consumes: `CANDIDATE_SHA`.
- Produces: draft PR to `main` plus full CI evidence.

- [ ] **Step 1: Open a draft PR**

Title:

```text
Release 1.0.0a4 — qualify integrated train for stable promotion
```

Base: `main`. Head: `release/1.0.0a4`.

The body must contain exactly these release-safety statements:

```text
DRAFT / NOT AUTHORIZED FOR MERGE
Physical Linux Mint/X11 acceptance pending.
Update/rollback qualification pending.
Final HUMAN_GATE from LEANDRO required before promotion/publication.
```

- [ ] **Step 2: Verify the diff boundary**

Expected: product code is the existing train tree; release-branch-only changes are version/docs/release-identity test.

- [ ] **Step 3: Require the full CI matrix on `CANDIDATE_SHA`**

Required successful steps:

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

Record the workflow run ID.

---

### Task 4: Create canonical R7 evidence without placeholders

**Files:**
- Create: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`

**Interfaces:**
- Consumes: exact current candidate SHA and CI run ID.
- Produces: one evidence document updated through the remaining gates.

- [ ] **Step 1: Resolve exact values in shell before writing the document**

```bash
export CANDIDATE_SHA="$(git rev-parse HEAD)"
export CI_RUN_ID="$(gh run list --commit "$CANDIDATE_SHA" --workflow CI --limit 1 --json databaseId --jq '.[0].databaseId')"
test -n "$CANDIDATE_SHA"
test -n "$CI_RUN_ID"
```

- [ ] **Step 2: Create the evidence document by expanding real variables**

```bash
cat > docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md <<EOF
# TriView 1.0.0a4 — R7 Qualification Evidence

## Candidate identity

- release candidate: \`1.0.0a4\`
- candidate branch: \`release/1.0.0a4\`
- candidate SHA: \`$CANDIDATE_SHA\`
- source train SHA: \`$TRAIN_SHA\`
- pre-promotion main SHA: \`$MAIN_SHA\`
- MCF baseline SHA: \`$MCF_SHA\`
- remote CI run: \`$CI_RUN_ID\`

## Gate status

| Gate | State |
|---|---|
| Remote CI | PASS |
| Physical Linux Mint/X11 | NOT_RUN |
| LEA-197 10-run matrix | NOT_RUN |
| MCF integration smoke | NOT_RUN |
| Update qualification | NOT_RUN |
| Rollback qualification | NOT_RUN |
| Blocker audit | BLOCKED |
| Final HUMAN_GATE | BLOCKED |
| Promotion/publication | BLOCKED |
EOF
```

- [ ] **Step 3: Commit and requalify CI**

```bash
git add docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md
git commit -m "docs: start R7 qualification evidence"
export CANDIDATE_SHA="$(git rev-parse HEAD)"
```

Because this changes the SHA, run full CI again. The physically tested candidate must be this newer exact SHA after it is GREEN.

---

### Task 5: Execute physical Linux Mint/X11 acceptance

**Files:**
- Modify: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`
- Modify after PASS: `docs/work/LEA-197.md`

**Interfaces:**
- Consumes: GREEN `CANDIDATE_SHA` from Task 4.
- Produces: exact-SHA physical evidence.

- [ ] **Step 1: Validate machine preconditions**

```bash
printf 'session=%s\n' "$XDG_SESSION_TYPE"
command -v xdotool
command -v xwininfo
command -v Xephyr
command -v xauth
```

Expected: X11 session and all commands found.

- [ ] **Step 2: Install the exact candidate**

```bash
export CANDIDATE_SHA="$(git rev-parse HEAD)"
TRIVIEW_CANDIDATE_REF="$CANDIDATE_SHA" bash scripts/install-train-candidate.sh
```

- [ ] **Step 3: Run LEA-197 terminal matrix**

Run five consecutive `x-terminal-emulator` open/verify/resize/close/reopen cycles. Record `T1` through `T5` individually as PASS or FAIL.

- [ ] **Step 4: Run LEA-197 Xed matrix**

Run five consecutive Xed cycles with the same procedure. Record `X1` through `X5` individually as PASS or FAIL.

- [ ] **Step 5: Verify LEA-197 invariants**

Record PASS/FAIL for:

```text
cross-window capture = 0
ATIVO only when embedded
EXTERNO only when actually external
resize/reopen deterministic
stable installation preserved
catalog preserved
```

- [ ] **Step 6: Run whole-product physical smoke**

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
MCF project detection is read-only
MCF binding persists references only
MCF token is not persisted
continuity route is displayed but not executed
diagnostic package is generated and sanitized
```

Any FAIL in a critical item blocks promotion.

- [ ] **Step 7: Update physical evidence**

Write every result to the R7 evidence document. If all LEA-197 entries PASS, update `docs/work/LEA-197.md` with the exact `CANDIDATE_SHA` and the ten-run matrix.

- [ ] **Step 8: Commit docs-only physical evidence and re-run CI**

```bash
git add docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md docs/work/LEA-197.md
git commit -m "docs: record 1.0.0a4 physical qualification"
export FINAL_CANDIDATE_SHA="$(git rev-parse HEAD)"
```

Verify the product-code tree is unchanged from the physically tested parent except documentation, then require full CI GREEN on `FINAL_CANDIDATE_SHA`.

---

### Task 6: Prove update and rollback safety

**Files:**
- Modify: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`

**Interfaces:**
- Consumes: candidate installation and existing stable lifecycle scripts.
- Produces: preservation/rollback evidence.

- [ ] **Step 1: Capture stable pre-test state**

```bash
readlink -f ~/.local/share/triview-workspace/current
cat ~/.local/share/triview-workspace/VERSION 2>/dev/null || true
sha256sum "${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace/workspaces.json"
```

Store the displayed release path/version/catalog hash in the evidence document.

- [ ] **Step 2: Dry-run rollback**

```bash
triview-workspace-rollback --dry-run
```

Expected: PASS without switching active release or modifying the catalog.

- [ ] **Step 3: Exercise candidate validation/activation through the supported path**

Use only the repository's existing candidate/update lifecycle. Confirm backup/provenance records are created before activation.

- [ ] **Step 4: Run candidate diagnostic**

```bash
triview-workspace-diagnose
```

Expected: sanitized diagnostic package.

- [ ] **Step 5: Execute controlled rollback**

```bash
triview-workspace-rollback
```

Expected: previous stable release is validated and restored.

- [ ] **Step 6: Verify post-rollback state**

```bash
readlink -f ~/.local/share/triview-workspace/current
sha256sum "${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace/workspaces.json"
```

Record the restored release and confirm intended user-data preservation.

- [ ] **Step 7: Record evidence**

Add backup/report identifiers and PASS/FAIL states to the R7 document. Do not include secrets, cookies, browser credentials or MCF tokens.

---

### Task 7: Complete blocker audit and release history

**Files:**
- Modify: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`
- Modify: `docs/product/RELEASE_HISTORY.md`
- GitHub metadata: close issue #26 only after evidence PASS.

**Interfaces:**
- Consumes: all completed gates.
- Produces: blocker-free final candidate.

- [ ] **Step 1: Re-scan blockers**

Required true statements:

```text
Critical = 0
High functional = 0
#68 remains BACKLOG_V2
#32 remains non-blocking for 1.0.0a4 under R7
#26 is satisfied by exact-SHA physical evidence
```

Stop if any statement is false.

- [ ] **Step 2: Close issue #26 with concrete evidence**

The closing comment must include the real candidate SHA, `5/5` terminal PASS, `5/5` Xed PASS, zero cross-window capture, final CI run ID and `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`.

- [ ] **Step 3: Add `1.0.0a4` to release history**

Document the MCF integration, train stabilization, physical Mint/X11 result, update/rollback result and MCF source-of-truth/read-only authority boundaries.

- [ ] **Step 4: Commit and run final full CI**

```bash
git add docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md docs/product/RELEASE_HISTORY.md
git commit -m "docs: complete 1.0.0a4 release qualification"
export FINAL_CANDIDATE_SHA="$(git rev-parse HEAD)"
```

Require all CI stages GREEN on `FINAL_CANDIDATE_SHA`.

---

### Task 8: Prepare the final HUMAN_GATE without merging

**Files:** PR metadata only.

**Interfaces:**
- Consumes: blocker-free `FINAL_CANDIDATE_SHA`.
- Produces: one immutable promotion request.

- [ ] **Step 1: Re-read final refs**

Verify `main == MAIN_SHA`, `MCF main == MCF_SHA`, and `release/1.0.0a4 == FINAL_CANDIDATE_SHA`. Any drift blocks the gate.

- [ ] **Step 2: Verify final evidence**

The R7 document must have no `NOT_RUN` for required qualification gates, no `FAIL`, and no unresolved release blocker.

- [ ] **Step 3: Mark PR ready for review**

Do this only after exact-head CI GREEN and complete evidence.

- [ ] **Step 4: Request the final HUMAN_GATE**

Resolve the SHA before composing the request:

```bash
export FINAL_CANDIDATE_SHA="$(git rev-parse HEAD)"
printf 'Authorize merge release/1.0.0a4@%s -> main@%s and authorize the resulting publish workflow to create v1.0.0a4 only if post-merge verification remains GREEN.\n' "$FINAL_CANDIDATE_SHA" "$MAIN_SHA"
```

No merge occurs until LEANDRO explicitly approves that exact target.

---

### Task 9: Promotion/publication — execute only after the future explicit HUMAN_GATE

**Files:** repository/PR state; follow-up evidence documentation if needed.

**Interfaces:**
- Consumes: exact future HUMAN_GATE.
- Produces: promoted `main` and verified `v1.0.0a4` release.

- [ ] **Step 1: Reconfirm authorized PR head**

Compare the PR head byte-for-byte with the SHA named in LEANDRO's authorization. Stop on mismatch.

- [ ] **Step 2: Merge using a merge commit**

Do not squash/rebase the qualified release history.

- [ ] **Step 3: Verify full CI on the resulting exact `main` SHA**

All CI stages must pass.

- [ ] **Step 4: Verify publication workflow**

Because `pyproject.toml` changed, `Publish stable release` must run verification before release creation. Require `verify = success` before accepting release publication.

- [ ] **Step 5: Verify immutable release identity**

Required final facts:

```text
latest release = v1.0.0a4
release target = exact authorized main SHA
project version = 1.0.0a4
```

- [ ] **Step 6: Fail forward, never rewrite history**

If post-merge verification fails, do not force-move `main` or the tag. Open a remediation branch; use the installed stable rollback mechanism on affected machines when needed.

## Self-Review

- Spec coverage: freeze/version, remote CI, physical Mint/X11, LEA-197, MCF smoke, update/rollback, blocker audit, final HUMAN_GATE and publication semantics all have concrete tasks.
- Placeholder scan: no `TBD`, `TODO`, angle-bracket SHA placeholders or unresolved pseudo-values remain; runtime identities are resolved via shell variables from actual refs.
- Interface consistency: `CANDIDATE_SHA` and `FINAL_CANDIDATE_SHA` always mean exact 40-character Git commit identities.
- Safety: Tasks 1-8 cannot merge or publish. Task 9 is explicitly conditional on a future exact HUMAN_GATE from LEANDRO.
