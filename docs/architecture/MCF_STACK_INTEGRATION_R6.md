# TriView × MCF — R6 Stack Qualification & Integration Evidence

**Status:** R2→R5 product stack integrated and qualified on `train/road-to-1.0`; R6 documentation follow-up pending merge at the time of this document commit.

## 1. Scope

R6 integrates the already-qualified TriView × MCF reconciliation stack into `train/road-to-1.0` without changing product semantics and without touching `main`.

Integration order was fixed and executed as:

`R2 #69 → R3 #70 → R4 #71 → R5 #72`

All four product PRs were merged with Git **merge commits**, never squash or rebase, preserving the qualified feature SHAs as ancestry.

## 2. Freeze Gate evidence

Immediately before the first product merge:

- TriView `train/road-to-1.0`: `17f1b11a36e09463d6ad9b3fdb0be0fc337c2f99` — PASS.
- MCF `main`: `5d79f488407c77f7b9f21ecfefb41ddfb3a52aef` — PASS.
- PR #69 head: `f8e7a4fa99e833f3779830f5537ac4fcfb152483` — open / not merged / mergeable.
- PR #70 head: `56b1b1d64cb255a60d315d7dc87132c354466de6` — open / not merged / mergeable.
- PR #71 head: `4b92086874d51ff9470ac978b12a213419d69f7a` — open / not merged / mergeable.
- PR #72 head: `2e79acafe2c8939583d36b63198511744a5800d4` — open / not merged / mergeable.
- Qualified head CI runs:
  - R2: `32004601425` — success.
  - R3: `32005523173` — success.
  - R4: `32007671759` — success.
  - R5: `32010748462` — success.
- R5 vs initial train: `ahead_by=34`, `behind_by=0` — PASS.

No preflight drift was found.

## 3. Sequential integration evidence

| Layer | PR | Qualified head | Merge commit on train | Post-merge CI | Result |
|---|---:|---|---|---:|---|
| R2 read-only bridge | #69 | `f8e7a4fa99e833f3779830f5537ac4fcfb152483` | `299975492999fe1c6175ac1cd3a7dc2eab75ee48` | `32013654768` | PASS |
| R3 Mission Cockpit | #70 | `56b1b1d64cb255a60d315d7dc87132c354466de6` | `87f42d64b7ca886bb09e9b909ec3b2dd46d9585f` | `32013871615` | PASS |
| R4 project-workspace binding | #71 | `4b92086874d51ff9470ac978b12a213419d69f7a` | `4a95ce0a047b24437e0ff91bb831305118b45d2d` | `32013979882` | PASS |
| R5 continuity/reconcile visual | #72 | `2e79acafe2c8939583d36b63198511744a5800d4` | `e091c6e1c7a3886dc829ba3886f5c73208b91f67` | `32014090488` | PASS |

Every post-merge CI ran the full repository workflow including compile, shell validation, pytest, X11 wheel integration, XTEST device integration and Xephyr containment integration.

## 4. Stacked-PR retarget behavior

After each parent layer was integrated, the child PR was retargeted from the parent feature branch to `train/road-to-1.0`.

GitHub briefly reported `mergeable=false` immediately after base changes while recomputing mergeability. The state subsequently stabilized to `mergeable=true` without branch rewrite or force push.

The effective diffs collapsed correctly:

- R3: 5 files — R3-only.
- R4: 7 files — R4-only.
- R5: 10 files — R5-only.

No parent-layer files were reintroduced as unintended deltas.

GitHub did not schedule a new PR workflow merely from each base retarget. This did not change product content: each prior parent integration merge commit had the same Git tree as the qualified parent feature head. The post-merge push CI on each newly integrated `train` state was therefore retained as the mandatory composition gate before advancing.

## 5. Final R2→R5 qualification

Qualified post-R5 `train` SHA:

`e091c6e1c7a3886dc829ba3886f5c73208b91f67`

Qualified post-R5 tree:

`a625015b467f92bb3cad8f5d3e1e944fa56a17e5`

The previously qualified R5 feature head `2e79acafe2c8939583d36b63198511744a5800d4` has the **same tree SHA**:

`a625015b467f92bb3cad8f5d3e1e944fa56a17e5`

Therefore the integrated product/test/documentation content inherited from R2→R5 is byte-for-byte tree-equivalent to the qualified R5 state; only merge ancestry differs.

Final post-R5 CI:

`32014090488` — `completed / success`.

## 6. Required modules present on train

Verified on `train/road-to-1.0` after R5:

- `src/triview_workspace/mcf_bridge.py` — present.
- `src/triview_workspace/mcf_cockpit.py` — present.
- `src/triview_workspace/mcf_binding.py` — present.
- `src/triview_workspace/mcf_continuity.py` — present.

## 7. Main branch isolation

TriView `main` after the R2→R5 integration remains:

`60b7e86dc738e1dc285e942951c67e41ac82b018`

This is the same pre-R6 main SHA. R6 performed no promotion, release or direct main mutation.

## 8. Invariant checklist

- [x] `main` remained out of scope.
- [x] `train/road-to-1.0` was the only product integration target.
- [x] R2→R5 were integrated only by merge commits.
- [x] No squash merge was used.
- [x] No rebase merge was used.
- [x] No force-push/history rewrite was used.
- [x] Qualified feature head SHAs remained unchanged.
- [x] Child PR diffs collapsed to their own layer after retargeting.
- [x] Full post-merge CI passed after every product-layer merge.
- [x] Final post-R5 tree equals the qualified R5 tree.
- [x] `mcf_bridge`, `mcf_cockpit`, `mcf_binding` and `mcf_continuity` are present on train.
- [x] No R6 product behavior was added.
- [x] No `.mcf` write capability was introduced by R6.
- [x] No mission/HUMAN_GATE/Standing Authorization mutation capability was introduced by R6.
- [x] No V2 multiagent isolation work was pulled into R6.

## 9. R6 documentation-only follow-up

The evidence branch `chore/triview-mcf-stack-integration-r6` was created from the exact R5 head before integration.

After R5 landed, comparing this branch against qualified `train@e091c6e1...` showed only R6 documentation files. PR #73 was then opened against `train/road-to-1.0` as the documentation-only integration vehicle.

The R6 documentation PR must pass fresh CI and be merged with a merge commit. That follow-up does not change the qualified product tree except for documentation files.

## 10. Promotion boundary

R6 does **not** authorize promotion to `main`.

Any merge/promotion from `train/road-to-1.0` to `main`, release creation, version promotion or production qualification requires a **separate HUMAN_GATE from LEANDRO** after the final R6 documentation integration is complete.
