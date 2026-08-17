from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from triview_workspace.mcf_continuity import (
    McfCheckpointProjection,
    McfGitObserver,
    normalize_github_repository,
)


CHECKPOINT_SHA = "a" * 40
HEAD_SHA = "b" * 40


def _checkpoint(
    *,
    repository: str = "leon337/project",
    branch: str = "feat/r5",
    sha: str | None = CHECKPOINT_SHA,
) -> McfCheckpointProjection:
    return McfCheckpointProjection(
        path="/project/.mcf/continuity/checkpoint-1.json",
        project_id="project-1",
        mission_id="mission-1",
        methodology_version="v1.1.0",
        methodology_ref="mcf-ref",
        repository=repository,
        branch=branch,
        checkpoint_sha=sha,
        captured_at="2026-08-17T08:00:00Z",
        transferability="TRANSFERABLE",
        resume_route_hint="FAST_RESUME",
        next_action="Continue",
        responsible_agent="MESTRE",
    )


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], tuple[int, str, str]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        call = tuple(args)
        self.calls.append(call)
        returncode, stdout, stderr = self.responses.get(call, (1, "", "unexpected command"))
        assert kwargs["shell"] is False
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["check"] is False
        assert kwargs["timeout"] == 3.0
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)


def _base_responses(
    root: Path,
    *,
    origin: str = "https://github.com/leon337/project.git",
    branch: str = "feat/r5",
    head: str = CHECKPOINT_SHA,
    status: str = "",
) -> dict[tuple[str, ...], tuple[int, str, str]]:
    prefix = ("git", "-C", str(root.resolve()))
    return {
        (*prefix, "config", "--get", "remote.origin.url"): (0, origin + "\n", ""),
        (*prefix, "rev-parse", "--abbrev-ref", "HEAD"): (0, branch + "\n", ""),
        (*prefix, "rev-parse", "HEAD"): (0, head + "\n", ""),
        (*prefix, "status", "--porcelain"): (0, status, ""),
        (*prefix, "cat-file", "-e", f"{CHECKPOINT_SHA}^{{commit}}"): (0, "", ""),
    }


def _assert_only_read_commands(calls: list[tuple[str, ...]]) -> None:
    forbidden = {
        "checkout",
        "switch",
        "reset",
        "merge",
        "rebase",
        "stash",
        "commit",
        "add",
        "clean",
        "pull",
        "push",
        "fetch",
        "branch",
        "tag",
    }
    for call in calls:
        assert call[0] == "git"
        assert not forbidden.intersection(call)


def test_normalize_github_repository_supports_common_https_and_ssh_forms() -> None:
    assert normalize_github_repository("https://github.com/owner/repo.git") == "owner/repo"
    assert normalize_github_repository("git@github.com:owner/repo.git") == "owner/repo"
    assert normalize_github_repository("ssh://git@github.com/owner/repo.git") == "owner/repo"
    assert normalize_github_repository("https://example.com/owner/repo.git") is None
    assert normalize_github_repository("") is None


def test_exact_git_state_is_observed_without_manufacturing_drift(tmp_path: Path) -> None:
    runner = FakeRunner(_base_responses(tmp_path))

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.live_state is not None
    assert evidence.live_state.repository == "leon337/project"
    assert evidence.live_state.branch == "feat/r5"
    assert evidence.live_state.head_sha == CHECKPOINT_SHA
    assert evidence.live_state.worktree_clean is True
    assert evidence.material_drift_explainable is False
    assert evidence.drift_reason is None
    assert evidence.reason_codes == ()
    _assert_only_read_commands(runner.calls)


def test_same_sha_on_different_branch_is_explainable_branch_drift(tmp_path: Path) -> None:
    runner = FakeRunner(_base_responses(tmp_path, branch="feat/other"))

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.material_drift_explainable is True
    assert evidence.drift_reason == "EXPLAINABLE_BRANCH_DRIFT"
    assert evidence.reason_codes == ()
    _assert_only_read_commands(runner.calls)


def test_clean_forward_ancestry_is_explainable(tmp_path: Path) -> None:
    responses = _base_responses(tmp_path, head=HEAD_SHA)
    prefix = ("git", "-C", str(tmp_path.resolve()))
    responses[(*prefix, "merge-base", "--is-ancestor", CHECKPOINT_SHA, HEAD_SHA)] = (0, "", "")
    runner = FakeRunner(responses)

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.material_drift_explainable is True
    assert evidence.drift_reason == "EXPLAINABLE_FORWARD_DRIFT"
    assert evidence.reason_codes == ()
    _assert_only_read_commands(runner.calls)


def test_clean_backward_ancestry_is_explainable(tmp_path: Path) -> None:
    responses = _base_responses(tmp_path, head=HEAD_SHA)
    prefix = ("git", "-C", str(tmp_path.resolve()))
    responses[(*prefix, "merge-base", "--is-ancestor", CHECKPOINT_SHA, HEAD_SHA)] = (1, "", "")
    responses[(*prefix, "merge-base", "--is-ancestor", HEAD_SHA, CHECKPOINT_SHA)] = (0, "", "")
    runner = FakeRunner(responses)

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.material_drift_explainable is True
    assert evidence.drift_reason == "EXPLAINABLE_BACKWARD_DRIFT"
    assert evidence.reason_codes == ()
    _assert_only_read_commands(runner.calls)


def test_clean_divergent_history_is_unexplained(tmp_path: Path) -> None:
    responses = _base_responses(tmp_path, head=HEAD_SHA)
    prefix = ("git", "-C", str(tmp_path.resolve()))
    responses[(*prefix, "merge-base", "--is-ancestor", CHECKPOINT_SHA, HEAD_SHA)] = (1, "", "")
    responses[(*prefix, "merge-base", "--is-ancestor", HEAD_SHA, CHECKPOINT_SHA)] = (1, "", "")
    runner = FakeRunner(responses)

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.material_drift_explainable is False
    assert evidence.drift_reason is None
    assert evidence.reason_codes == ("UNEXPLAINED_DIVERGENCE",)
    _assert_only_read_commands(runner.calls)


def test_dirty_worktree_is_never_explainable(tmp_path: Path) -> None:
    runner = FakeRunner(_base_responses(tmp_path, head=HEAD_SHA, status=" M changed.py\n"))

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.live_state is not None
    assert evidence.live_state.worktree_clean is False
    assert evidence.material_drift_explainable is False
    assert evidence.reason_codes == ("WORKTREE_DIRTY",)
    assert not any("merge-base" in call for call in runner.calls)
    _assert_only_read_commands(runner.calls)


def test_repository_identity_mismatch_is_not_explainable(tmp_path: Path) -> None:
    runner = FakeRunner(
        _base_responses(tmp_path, origin="git@github.com:other/project.git", head=HEAD_SHA)
    )

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.live_state is not None
    assert evidence.live_state.repository == "other/project"
    assert evidence.material_drift_explainable is False
    assert evidence.reason_codes == ("REPOSITORY_IDENTITY_MISMATCH",)
    assert not any("merge-base" in call for call in runner.calls)
    _assert_only_read_commands(runner.calls)


def test_missing_checkpoint_commit_is_unexplained_evidence(tmp_path: Path) -> None:
    responses = _base_responses(tmp_path, head=HEAD_SHA)
    prefix = ("git", "-C", str(tmp_path.resolve()))
    responses[(*prefix, "cat-file", "-e", f"{CHECKPOINT_SHA}^{{commit}}")] = (1, "", "missing")
    runner = FakeRunner(responses)

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.live_state is not None
    assert evidence.material_drift_explainable is False
    assert evidence.reason_codes == ("CHECKPOINT_COMMIT_UNAVAILABLE",)
    _assert_only_read_commands(runner.calls)


def test_missing_or_unparseable_origin_makes_live_git_unavailable(tmp_path: Path) -> None:
    runner = FakeRunner(_base_responses(tmp_path, origin="file:///tmp/project"))

    evidence = McfGitObserver(runner=runner).observe(tmp_path, _checkpoint())

    assert evidence.live_state is None
    assert evidence.material_drift_explainable is False
    assert evidence.reason_codes == ("LIVE_GIT_UNAVAILABLE",)
    _assert_only_read_commands(runner.calls)
