# TriView × MCF — R6 Stack Qualification & Integration Design

**Status:** design approved by LEANDRO; implementation not started.

**TriView integration baseline:** `train/road-to-1.0@17f1b11a36e09463d6ad9b3fdb0be0fc337c2f99`

**Stack heads:**
- R2 / PR #69: `f8e7a4fa99e833f3779830f5537ac4fcfb152483`
- R3 / PR #70: `56b1b1d64cb255a60d315d7dc87132c354466de6`
- R4 / PR #71: `4b92086874d51ff9470ac978b12a213419d69f7a`
- R5 / PR #72: `2e79acafe2c8939583d36b63198511744a5800d4`

**MCF semantic baseline:** `main@5d79f488407c77f7b9f21ecfefb41ddfb3a52aef` / v1.1.0.

**R6 evidence branch:** `chore/triview-mcf-stack-integration-r6`, created from the exact R5 head so it can collapse to documentation-only after R5 is integrated into `train`.

## Objective

Integrate the already-qualified R2→R5 TriView × MCF stack into `train/road-to-1.0` without changing feature semantics, without touching `main`, and while preserving review boundaries and ancestry across the stacked PRs.

R6 is an integration/qualification phase. It must not add new product behavior.

## Invariants

1. `main` is out of scope.
2. `train/road-to-1.0` is the only integration target.
3. No R2-R5 production semantics may be changed during R6 unless a regression is discovered and separately fixed/tested.
4. No write to `.mcf`, no mission mutation, no HUMAN_GATE mutation, no Standing Authorization mutation, no Git mutation from the TriView MCF runtime paths.
5. `WorkspaceSpec`, `LayoutSpec`, `WorkspaceCatalog`, `workspaces.json`, and the R4 binding schema remain unchanged.
6. The MCF semantic baseline must still resolve to `5d79f488...` before the first merge. Any drift pauses R6 for reconciliation.
7. The `train` ref must still resolve to `17f1b11...` before the first merge. Any drift pauses R6 for requalification.

## Integration strategy

Use sequential stacked-PR integration:

`R2 #69 → R3 #70 → R4 #71 → R5 #72`

Each layer is integrated only after the previous layer is present in `train` and the child PR has been retargeted to `train`.

### Mandatory merge method

Use **merge commits only** for #69, #70, #71, and #72.

Do not use squash or rebase merges during R6. The child PRs rely on exact parent ancestry. Merge commits preserve the original feature SHAs so that, after retargeting, each child PR naturally collapses to its own delta.

## Preflight / Freeze Gate

Immediately before the first merge:

- verify `train/road-to-1.0 == 17f1b11a36e09463d6ad9b3fdb0be0fc337c2f99`;
- verify MCF `main == 5d79f488407c77f7b9f21ecfefb41ddfb3a52aef`;
- verify PRs #69-#72 are open, not merged, and retain their approved heads;
- verify each current head has a successful full CI run;
- verify the full R2→R5 stack is ahead of `train` with `behind_by == 0`.

If any check fails, stop before mutation.

## Per-layer sequence

For each layer:

1. Confirm PR is mergeable and its head is the expected qualified SHA.
2. Confirm the PR diff contains only that layer's intended delta relative to its current base.
3. Require a fresh successful CI run for that exact head/base state where GitHub schedules one after retargeting.
4. Merge with a merge commit.
5. Verify the resulting `train` head includes the layer and that the repository workflow on the resulting integration state is successful when triggered.
6. Only then retarget the next stacked PR to `train`.

### R2

Merge #69 into `train` first. No retarget is needed.

### R3

After R2 lands, retarget #70 from `feat/triview-mcf-bridge-r2` to `train`. Its effective diff must reduce to R3 only.

### R4

After R3 lands, retarget #71 from `feat/triview-mcf-cockpit-r3` to `train`. Its effective diff must reduce to R4 only.

### R5

After R4 lands, retarget #72 from `feat/triview-mcf-binding-r4` to `train`. Its effective diff must reduce to R5 only.

## Final stack qualification gate

After R5 lands, before R6 documentation is integrated:

- run/observe fresh full CI on the resulting `train` head;
- verify presence of `mcf_bridge.py`, `mcf_cockpit.py`, `mcf_binding.py`, and `mcf_continuity.py`;
- compare the production/test/documentation content inherited from R2-R5 with the previously qualified R5 tree;
- verify no unintended files changed outside the known R2-R5 set;
- verify `main` still points to its pre-R6 SHA;
- record all four merge SHAs, CI evidence, and the qualified stack SHA.

## R6 evidence branch and documentation integration

The branch `chore/triview-mcf-stack-integration-r6` was created from the exact R5 head before integration and initially contains only this design document beyond R5.

After the R5 stack qualification gate passes:

1. retarget/open the R6 documentation PR against `train`;
2. confirm its effective diff has collapsed to documentation-only;
3. add `docs/architecture/MCF_STACK_INTEGRATION_R6.md` containing:
   - preflight evidence;
   - PR/head/base table;
   - R2-R5 merge SHAs;
   - CI runs;
   - qualified post-R5 `train` SHA;
   - final `main` SHA proving no promotion occurred;
   - invariant checklist;
   - explicit statement that promotion to `main` requires a separate HUMAN_GATE;
4. run fresh CI for the docs-only R6 head;
5. integrate the R6 documentation PR into `train` with a merge commit;
6. verify final `train` CI if triggered and record the final documentation merge SHA.

This fifth merge is documentation-only and does not alter product behavior.

## Failure handling

R6 is fail-closed.

Stop the sequence if any of these occurs:

- unexpected `train` or MCF drift;
- PR head changes unexpectedly;
- mergeability becomes false/unknown due to conflict;
- child PR diff contains parent-layer changes after retargeting;
- CI fails;
- final tree contains unexplained changes;
- R6 evidence branch does not reduce to docs-only after R5 integration;
- any operation would require squash/rebase or force-pushing a qualified branch.

A stopped R6 does not auto-repair by rewriting history. Any correction becomes a new, explicit change with its own tests and review.

## Non-goals

R6 does not:

- promote to `main`;
- create a release;
- implement new UI or MCF capabilities;
- execute `FAST_RESUME`, `RECONCILE`, or `RECOVER_MCF_PROJECT`;
- implement V2 multiagent isolation;
- rewrite or squash the R2-R5 history.

## Success criterion

R6 is complete only when `train/road-to-1.0` contains the full R2-R5 stack through sequential merge commits, the post-R5 stack qualification is green, the R6 evidence is integrated as a documentation-only follow-up, all invariants are verified, and `main` remains untouched.
