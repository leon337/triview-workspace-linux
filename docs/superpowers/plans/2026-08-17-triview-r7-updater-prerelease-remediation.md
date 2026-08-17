# R7 Minimal Prerelease Updater Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the controlled testing-manifest updater accept only the approved simple PEP 440 prerelease forms (`aN`, `bN`, `rcN`) while preserving every currently accepted version form and every existing lifecycle/security invariant.

**Architecture:** Keep version validation inside `read_testing_manifest()` in `scripts/update-core.sh` and extend only its existing regular expression. Drive the change through `tests/test_update_channel.py` with a test-only RED commit, a one-line production GREEN fix, exact-head CI, and a separate integration gate before the remediation can enter `release/1.0.0a4`.

**Tech Stack:** Bash, embedded Python 3, Python `re`, pytest, GitHub Actions, Git/GitHub pull requests.

## Global Constraints

- Design source release head is exactly `678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac`.
- Frozen pre-remediation product candidate is `a8fd3209d6315cc7cc1870220b6c79e7296b45b3` and becomes historical-only after this lifecycle-code remediation is integrated.
- Preserve all existing accepted forms: `1.0.0`, `1.0.0-test.1`, and `1.0.0+build.1`.
- Add only lowercase simple prereleases: `1.0.0a4`, `1.0.0b2`, and `1.0.0rc1`, generalized as `aN`, `bN`, `rcN` where `N` is one or more decimal digits.
- Continue rejecting at minimum: `1.0`, `v1.0.0`, `1.0.0a`, `1.0.0b`, `1.0.0rc`, `1.0.0dev1`, `1.0.0.dev1`, `1.0.0post1`, `1.0.0.post1`, `1.0.0a4+build`, and `1.0.0rc1+build`.
- Do not add dependencies or implement a general PEP 440 parser.
- Do not enable `config/update-channels/testing.json` or change its schema/content.
- Do not change stable-channel discovery, SHA pinning, archive selection, download, extraction, compile, activation, backup, rollback, lifecycle locking, MCF behavior, `main`, tags, or public releases.
- Production change is restricted to the `version` regex inside `read_testing_manifest()` in `scripts/update-core.sh`.
- If any second production file appears necessary, stop and return to design review instead of expanding scope.
- PR #74 must remain draft throughout remediation development and qualification.
- The remediation PR targets `release/1.0.0a4`, never `main`.
- No remediation merge is authorized by implementation approval alone; integration requires a fresh HUMAN_GATE.

---

## File map

- Modify: `tests/test_update_channel.py` — add the RED/GREEN grammar contract and reuse the existing controlled-manifest dry-run path.
- Modify: `scripts/update-core.sh` — change only the testing-manifest `version` regular expression.
- No other production file is permitted to change under this plan.
- No release ledger update occurs before the remediation is integrated; evidence is kept in the remediation PR until the later integration gate.

---

### Task 1: Create the isolated remediation branch and prove RED

**Files:**
- Modify: `tests/test_update_channel.py`
- Read only: `scripts/update-core.sh`

**Interfaces:**
- Consumes: existing `MANIFEST`, `CORE`, and the repository testing-channel fixture in `tests/test_update_channel.py`.
- Produces: `_run_enabled_testing_manifest_dry_run(tmp_path: Path, version: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]` plus positive/negative grammar tests used by Task 2.

- [ ] **Step 1: Revalidate the frozen execution baseline before creating any implementation branch**

Run:

```bash
git fetch origin
RELEASE_SHA="$(git rev-parse origin/release/1.0.0a4)"
MAIN_SHA="$(git rev-parse origin/main)"
printf 'release=%s\nmain=%s\n' "$RELEASE_SHA" "$MAIN_SHA"
test "$RELEASE_SHA" = "678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac"
test "$MAIN_SHA" = "60b7e86dc738e1dc285e942951c67e41ac82b018"
```

Expected: both `test` commands exit 0. If either SHA differs, stop before branch creation and requalify the design baseline.

- [ ] **Step 2: Create an isolated worktree and implementation branch from the exact release head**

Use the required `superpowers:using-git-worktrees` sub-skill, then run the equivalent of:

```bash
git worktree add ../triview-r7-updater-remediation -b fix/triview-r7-updater-prerelease-version 678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac
cd ../triview-r7-updater-remediation
test "$(git rev-parse HEAD)" = "678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac"
```

Expected: branch `fix/triview-r7-updater-prerelease-version` exists only in the isolated worktree and HEAD matches the exact approved base SHA.

- [ ] **Step 3: Add the test helper and complete approved version matrices before production code changes**

In `tests/test_update_channel.py`, add `import pytest` with the other imports, then add this helper immediately before the existing testing-manifest tests:

```python
def _run_enabled_testing_manifest_dry_run(
    tmp_path: Path,
    version: str,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    enabled_manifest = tmp_path / "testing-enabled.json"
    data: dict[str, object] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    data["enabled"] = True
    data["status"] = "test-fixture-enabled"
    data["version"] = version
    enabled_manifest.write_text(json.dumps(data), encoding="utf-8")

    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "TRIVIEW_APP_ROOT": str(tmp_path / "app"),
            "TRIVIEW_BACKUP_ROOT": str(tmp_path / "backups"),
            "TRIVIEW_TEST_MANIFEST_FILE": str(enabled_manifest),
            "TRIVIEW_NO_RESULT_UI": "1",
        }
    )

    completed = subprocess.run(
        ["bash", str(CORE), "--testing", "--dry-run"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed, data
```

Add the supported-version matrix:

```python
@pytest.mark.parametrize(
    "version",
    [
        "1.0.0",
        "1.0.0-test.1",
        "1.0.0+build.1",
        "1.0.0a4",
        "1.0.0b2",
        "1.0.0rc1",
    ],
)
def test_explicit_testing_accepts_approved_version_grammar(
    tmp_path: Path,
    version: str,
) -> None:
    completed, data = _run_enabled_testing_manifest_dry_run(tmp_path, version)
    output = completed.stdout + completed.stderr

    assert completed.returncode == 0
    assert "Candidato autorizado: LEA-197" in output
    assert f"versão {version}" in output
    assert str(data["ref"]) in output
    assert "/archive/refs/heads/main.tar.gz" not in output
    assert not (tmp_path / "app" / "current").exists()
```

Add the explicit rejection matrix:

```python
@pytest.mark.parametrize(
    "version",
    [
        "1.0",
        "v1.0.0",
        "1.0.0a",
        "1.0.0b",
        "1.0.0rc",
        "1.0.0dev1",
        "1.0.0.dev1",
        "1.0.0post1",
        "1.0.0.post1",
        "1.0.0a4+build",
        "1.0.0rc1+build",
    ],
)
def test_explicit_testing_rejects_out_of_scope_version_grammar(
    tmp_path: Path,
    version: str,
) -> None:
    completed, _data = _run_enabled_testing_manifest_dry_run(tmp_path, version)
    output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert "versão inválida" in output
    assert not (tmp_path / "app" / "current").exists()
```

Do not delete or weaken `test_disabled_repository_manifest_blocks_explicit_testing()` or the existing enabled-manifest test.

- [ ] **Step 4: Run the targeted test file and verify the intended RED shape**

Run:

```bash
pytest tests/test_update_channel.py -q
```

Expected: the legacy accepted forms and rejection matrix pass, while the positive cases `1.0.0a4`, `1.0.0b2`, and `1.0.0rc1` fail because the current validator reports `versão inválida`. No unrelated test in `tests/test_update_channel.py` should fail.

- [ ] **Step 5: Commit only the RED test delta**

Run:

```bash
git add tests/test_update_channel.py
git diff --cached --name-only
test "$(git diff --cached --name-only)" = "tests/test_update_channel.py"
git commit -m "test: cover updater prerelease version grammar"
RED_SHA="$(git rev-parse HEAD)"
printf 'RED_SHA=%s\n' "$RED_SHA"
```

Expected: one test-only commit. `scripts/update-core.sh` remains byte-for-byte unchanged from `678ed509…`.

- [ ] **Step 6: Push the RED branch and open a draft remediation PR against the release branch**

Run:

```bash
git push -u origin fix/triview-r7-updater-prerelease-version
gh pr create \
  --draft \
  --base release/1.0.0a4 \
  --head fix/triview-r7-updater-prerelease-version \
  --title "R7: accept minimal prerelease versions in testing manifest" \
  --body "R7 updater prerelease remediation. RED first: tests add the approved aN/bN/rcN grammar while production validation is intentionally unchanged. This PR targets release/1.0.0a4 only and is not authorized for merge. PR #74 remains draft."
REMEDIATION_PR="$(gh pr view --head fix/triview-r7-updater-prerelease-version --json number --jq .number)"
printf 'REMEDIATION_PR=%s\n' "$REMEDIATION_PR"
```

Expected: a draft PR targeting `release/1.0.0a4`, never `main`.

- [ ] **Step 7: Capture remote RED evidence before touching production code**

Run:

```bash
gh pr checks "$REMEDIATION_PR" --watch
```

Expected: CI fails at pytest because the new positive prerelease cases are rejected. Inspect the failing run and confirm the failure is limited to the new approved prerelease grammar; infrastructure, shell syntax, and unrelated tests must not be the root cause.

Record the actual RED commit SHA and CI run ID in the PR body or a PR comment. Do not modify release documentation in this task.

---

### Task 2: Apply the minimal GREEN validator change

**Files:**
- Modify: `scripts/update-core.sh`
- Test: `tests/test_update_channel.py`

**Interfaces:**
- Consumes: Task 1's grammar tests and existing `read_testing_manifest()` contract.
- Produces: testing-manifest `version` validation that accepts legacy forms plus lowercase `aN`, `bN`, `rcN`, and nothing else added by this remediation.

- [ ] **Step 1: Replace only the approved version regular expression**

In `scripts/update-core.sh`, find this exact line inside the embedded Python of `read_testing_manifest()`:

```python
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", str(data["version"])):
```

Replace it with exactly:

```python
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+|[-+][A-Za-z0-9.-]+)?", str(data["version"])):
```

Leave the following line unchanged:

```python
    raise SystemExit("versão inválida")
```

Do not change any other validation rule or shell control flow.

- [ ] **Step 2: Validate Bash syntax immediately after the one-line production edit**

Run:

```bash
bash -n scripts/update-core.sh
```

Expected: exit 0 with no output.

- [ ] **Step 3: Run the targeted updater tests and verify GREEN**

Run:

```bash
pytest tests/test_update_channel.py -q
```

Expected: all tests in `tests/test_update_channel.py` pass, including legacy accepted forms, the three new prerelease forms, all explicit rejection cases, disabled-manifest fail-closed behavior, full-SHA pinning, and dry-run non-activation assertions.

- [ ] **Step 4: Run the lifecycle-focused regression slice before the full suite**

Run:

```bash
pytest \
  tests/test_update_channel.py \
  tests/test_stable_update_safety.py \
  tests/test_stable_rollback.py \
  tests/test_stable_rollback_provenance.py \
  tests/test_stable_lifecycle_lock.py \
  -q
```

Expected: PASS. Any failure outside the new version grammar is a blocker; do not broaden the implementation to fix unrelated lifecycle behavior under this remediation.

- [ ] **Step 5: Prove the complete intended delta is exactly two files before committing GREEN**

Run:

```bash
{
  git diff --name-only 678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac...HEAD
  git diff --name-only
} | sort -u > /tmp/triview-r7-remediation-files.txt
cat /tmp/triview-r7-remediation-files.txt
printf '%s\n' scripts/update-core.sh tests/test_update_channel.py > /tmp/triview-r7-remediation-expected.txt
diff -u /tmp/triview-r7-remediation-expected.txt /tmp/triview-r7-remediation-files.txt
```

Expected: `diff` exits 0 and the complete history-plus-working-tree delta is exactly:

```text
scripts/update-core.sh
tests/test_update_channel.py
```

No second production file is allowed.

- [ ] **Step 6: Commit the minimal production fix**

Run:

```bash
git add scripts/update-core.sh
git diff --cached --name-only
test "$(git diff --cached --name-only)" = "scripts/update-core.sh"
git commit -m "fix: accept simple prerelease versions in testing manifest"
GREEN_SHA="$(git rev-parse HEAD)"
printf 'GREEN_SHA=%s\n' "$GREEN_SHA"
git push
```

Expected: the GREEN production commit modifies only `scripts/update-core.sh`; the test contract remains in the preceding RED commit.

- [ ] **Step 7: Require fresh exact-head CI on the GREEN remediation head**

Run:

```bash
gh pr checks "$REMEDIATION_PR" --watch
```

Expected: the exact `GREEN_SHA` passes the complete repository CI matrix, including compile, shell validation, pytest, X11 wheel, XTEST, and Xephyr.

If CI fails, investigate the root cause before changing code. Do not merge, force, or rewrite history to bypass a failing gate.

---

### Task 3: Qualify the remediation PR and prepare the integration HUMAN_GATE

**Files:**
- Read/compare: `scripts/update-core.sh`
- Read/compare: `tests/test_update_channel.py`
- Metadata only: remediation PR and PR #74

**Interfaces:**
- Consumes: Task 2 exact-head GREEN CI.
- Produces: a merge-ready-but-still-draft remediation PR with auditable RED/GREEN evidence and no release integration yet.

- [ ] **Step 1: Recheck that the release branch did not drift during remediation development**

Run:

```bash
git fetch origin
CURRENT_RELEASE_SHA="$(git rev-parse origin/release/1.0.0a4)"
printf 'CURRENT_RELEASE_SHA=%s\n' "$CURRENT_RELEASE_SHA"
test "$CURRENT_RELEASE_SHA" = "678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac"
```

Expected: exact match. If the release branch moved, stop; rebase/requalification must be designed explicitly. Do not force or silently replay the remediation.

- [ ] **Step 2: Verify the complete remediation diff is restricted to the two approved files**

Run:

```bash
git diff --name-only 678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac...HEAD
```

Expected exactly:

```text
scripts/update-core.sh
tests/test_update_channel.py
```

Then inspect production patch:

```bash
git diff 678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac...HEAD -- scripts/update-core.sh
```

Expected: only the single `version` regex changes in production code.

- [ ] **Step 3: Verify PR #74 is still draft and still points to the unchanged release head**

Run:

```bash
gh pr view 74 --json state,isDraft,baseRefName,headRefName,headRefOid --jq '{state,isDraft,baseRefName,headRefName,headRefOid}'
```

Expected semantic state:

```text
state = OPEN
isDraft = true
baseRefName = main
headRefName = release/1.0.0a4
headRefOid = 678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac
```

Any change to `main` promotion state is out of scope and blocks completion of this task.

- [ ] **Step 4: Update only the remediation PR description with exact evidence**

Resolve immutable identifiers first:

```bash
RED_SHA="$(git rev-list --reverse 678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac..HEAD | sed -n '1p')"
GREEN_SHA="$(git rev-parse HEAD)"
printf 'RED_SHA=%s\nGREEN_SHA=%s\n' "$RED_SHA" "$GREEN_SHA"
```

Use GitHub Actions or `gh run list --commit "$RED_SHA"` and `gh run list --commit "$GREEN_SHA"` to obtain the actual RED and GREEN CI run IDs. Update only the remediation PR body with the approved minimal grammar, exact RED/CI evidence, exact GREEN/CI evidence, exact two-file diff, testing-manifest-disabled statement, PR #74 draft statement, and explicit no-integration authorization statement.

Do not commit this evidence into `release/1.0.0a4`.

- [ ] **Step 5: Run the final verification-before-completion gate**

Use `superpowers:verification-before-completion`, then independently verify:

```bash
bash -n scripts/update-core.sh
pytest tests/test_update_channel.py -q
git status --short
git diff --name-only 678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac...HEAD
```

Expected: shell validation PASS; targeted updater tests PASS; clean worktree; exactly two changed files; latest remediation CI full matrix GREEN; remediation PR still draft/unmerged; release branch still at `678ed509…`; `main` still at `60b7e86…`.

- [ ] **Step 6: Stop at the integration HUMAN_GATE**

Do not mark the remediation PR ready and do not merge it under the implementation authorization.

Report the exact remediation PR number, RED SHA/run, GREEN SHA/run, changed files, release SHA, PR #74 state, and `main` SHA. Request a fresh explicit HUMAN_GATE to integrate the remediation into `release/1.0.0a4`.

---

### Task 4: Integrate the qualified remediation and renew the R7 product candidate — gated, not executable without a fresh HUMAN_GATE

**Files:**
- Merge only: qualified remediation PR
- Later evidence update: `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md`
- Metadata only: PR #74

**Interfaces:**
- Consumes: Task 3 qualified remediation head plus fresh human authorization.
- Produces: a new immutable R7 product candidate SHA on `release/1.0.0a4`, replacing `a8fd3209…` for all remaining physical/update qualification.

- [ ] **Step 1: Revalidate the remediation PR immediately before integration**

Required state:

```text
base = release/1.0.0a4
head = fix/triview-r7-updater-prerelease-version
mergeable = true
exact head CI = success
release/1.0.0a4 = 678ed509ad8b9c34a4e85aa0f6e1f7d8260829ac
```

If any value differs, stop. Never force, squash, rebase, or bypass exact-head validation.

- [ ] **Step 2: After and only after the fresh HUMAN_GATE, integrate with a merge commit protected by expected head SHA**

Use GitHub merge method `merge`, not squash or rebase. After the merge, refresh the remote ref and capture the merge commit as the new candidate:

```bash
git fetch origin release/1.0.0a4
NEW_PRODUCT_SHA="$(git rev-parse origin/release/1.0.0a4)"
printf 'NEW_PRODUCT_SHA=%s\n' "$NEW_PRODUCT_SHA"
```

The new product candidate is the release-branch merge commit containing the lifecycle fix and its tests. `a8fd3209…` becomes historical evidence only.

- [ ] **Step 3: Require the full push CI on the exact new release-branch SHA**

Expected complete success:

```text
Compile
Validate shell scripts
Tests
X11 wheel integration
XTEST device integration
Xephyr containment integration
```

Do not freeze `NEW_PRODUCT_SHA` as the renewed candidate until this exact push CI concludes success.

- [ ] **Step 4: Update R7 evidence without confusing product SHA with evidence-head SHA**

Update `docs/architecture/TRIVIEW_RELEASE_1.0.0A4_QUALIFICATION_R7.md` to record the old product candidate as historical/pre-remediation, the remediation RED and GREEN evidence, the remediation merge commit as `NEW_PRODUCT_SHA`, the exact push CI for that SHA, and reset all physical qualification tied to the old candidate to `NOT_RUN`. The pre-publication updater gate becomes no longer parser-blocked but remains `NOT_RUN` until exercised through an explicitly enabled temporary controlled manifest on the physical qualification machine. PR #74 remains draft.

A later docs-only evidence commit may advance the branch head; it must not replace `NEW_PRODUCT_SHA` as the immutable product candidate identity.

- [ ] **Step 5: Continue R7 from the renewed candidate rather than promoting**

No merge to `main`, no `v1.0.0a4` tag, and no GitHub Release are part of this task. Resume the physical runbook and lifecycle qualification using only `NEW_PRODUCT_SHA`, then return to the existing R7 final promotion HUMAN_GATE after all required gates are PASS.
