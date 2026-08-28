# TriView × MCF R6 Stack Qualification & Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the already-qualified R2→R5 TriView × MCF stack into `train/road-to-1.0` through sequential merge commits, preserve stacked ancestry, qualify the final train state, and integrate R6 evidence as documentation-only.

**Architecture:** R6 changes no product behavior. It is a fail-closed integration pipeline over PRs #69→#72, followed by a docs-only R6 evidence merge. Every mutating step is preceded and followed by exact-SHA, diff, and CI gates.

**Tech Stack:** GitHub pull requests, GitHub Actions, Git merge commits, existing Python/pytest/X11 CI.

## Global Constraints

- `main` is out of scope and must remain unchanged.
- `train/road-to-1.0` is the only product integration target.
- Mandatory merge method for #69–#72: `merge` (merge commit), never squash/rebase.
- Expected initial train SHA: `17f1b11a36e09463d6ad9b3fdb0be0fc337c2f99`.
- Expected MCF semantic SHA: `5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`.
- Expected heads: #69 `f8e7a4fa99e833f3779830f5537ac4fcfb152483`; #70 `56b1b1d64cb255a60d315d7dc87132c354466de6`; #71 `4b92086874d51ff9470ac978b12a213419d69f7a`; #72 `2e79acafe2c8939583d36b63198511744a5800d4`.
- Any unexplained ref drift, changed PR head, CI failure, conflict, non-collapsing child diff, or need for history rewrite stops R6.

---

### Task 1: Freeze Gate

**Files:** none.

- [ ] Verify `train/road-to-1.0` equals the expected initial SHA.
- [ ] Verify MCF `main` equals the expected semantic SHA.
- [ ] Verify PRs #69–#72 are open, not merged, mergeable, and retain expected heads.
- [ ] Verify each expected PR head has a successful full workflow run.
- [ ] Compare R5 head against initial train and require `behind_by == 0`.
- [ ] Stop before mutation if any check fails.

### Task 2: Integrate R2 / PR #69

**Files:** R2 delta only.

- [ ] Confirm #69 base is `train/road-to-1.0`, head is expected R2 SHA, and diff is R2-only.
- [ ] Merge #69 with merge method `merge` and `expected_head_sha` set.
- [ ] Verify #69 is merged and capture merge SHA/new train SHA.
- [ ] Verify workflow on the resulting train integration state when available; require success before proceeding.

### Task 3: Integrate R3 / PR #70

**Files:** R3 delta only.

- [ ] Retarget #70 base to `train/road-to-1.0`.
- [ ] Verify head remains the expected R3 SHA and effective diff collapses to R3-only.
- [ ] Require successful CI for the exact retargeted state/head.
- [ ] Merge #70 with method `merge` and expected head SHA.
- [ ] Capture merge SHA/new train SHA and verify post-merge workflow success when available.

### Task 4: Integrate R4 / PR #71

**Files:** R4 delta only.

- [ ] Retarget #71 base to `train/road-to-1.0`.
- [ ] Verify head remains the expected R4 SHA and effective diff collapses to R4-only.
- [ ] Require successful CI for the exact retargeted state/head.
- [ ] Merge #71 with method `merge` and expected head SHA.
- [ ] Capture merge SHA/new train SHA and verify post-merge workflow success when available.

### Task 5: Integrate R5 / PR #72

**Files:** R5 delta only.

- [ ] Retarget #72 base to `train/road-to-1.0`.
- [ ] Verify head remains the expected R5 SHA and effective diff collapses to R5-only.
- [ ] Require successful CI for the exact retargeted state/head.
- [ ] Merge #72 with method `merge` and expected head SHA.
- [ ] Capture merge SHA/new train SHA and verify post-merge workflow success when available.

### Task 6: Qualify the integrated R2→R5 stack

**Files:** none.

- [ ] Verify final post-R5 `train` workflow is fully green.
- [ ] Verify `mcf_bridge.py`, `mcf_cockpit.py`, `mcf_binding.py`, and `mcf_continuity.py` exist on train.
- [ ] Compare integrated train content against qualified R5 content and require no unexplained product/test differences.
- [ ] Verify `main` still equals its pre-R6 SHA.
- [ ] Record merge SHAs, workflow run IDs, and qualified post-R5 train SHA.

### Task 7: Integrate R6 evidence as docs-only

**Files:**
- Existing: `docs/superpowers/specs/2026-08-17-triview-mcf-stack-integration-r6-design.md`
- Existing: `docs/superpowers/plans/2026-08-17-triview-mcf-stack-integration-r6.md`
- Create: `docs/architecture/MCF_STACK_INTEGRATION_R6.md`

- [ ] Retarget/open R6 branch against `train/road-to-1.0` only after R5 qualification passes.
- [ ] Confirm its effective diff is documentation-only.
- [ ] Create `MCF_STACK_INTEGRATION_R6.md` with preflight evidence, all merge SHAs, CI run IDs, qualified train SHA, main SHA, invariant checklist, and explicit separate HUMAN_GATE requirement for promotion to main.
- [ ] Require fresh CI success for the docs-only R6 head.
- [ ] Merge the R6 documentation PR with merge method `merge`.
- [ ] Verify final train state/CI and record final documentation merge SHA.

### Task 8: Completion Gate

- [ ] Re-read PR states and final train/main refs from GitHub.
- [ ] Confirm #69–#72 are merged, R6 docs are integrated, `main` is unchanged, and no release/promotion occurred.
- [ ] Report R6 as complete only with fresh evidence from the final state.
