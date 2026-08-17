from __future__ import annotations

from triview_workspace.mcf_continuity import (
    McfLiveRepositoryState,
    McfResumeDecisionInput,
    decide_resume_route,
)


def _input(**overrides: object) -> McfResumeDecisionInput:
    values: dict[str, object] = {
        "checkpoint_available": True,
        "live_repository_state": McfLiveRepositoryState(
            repository="leon337/project",
            branch="feat/r5",
            head_sha="a" * 40,
            worktree_clean=True,
        ),
        "authoritative_records_resolved": True,
        "methodology_pin_valid": True,
        "checkpoint_integrity_valid": True,
        "transferability": "TRANSFERABLE",
        "checkpoint_repository": "leon337/project",
        "checkpoint_branch": "feat/r5",
        "checkpoint_sha": "a" * 40,
        "material_drift_explainable": False,
        "drift_reason": None,
    }
    values.update(overrides)
    return McfResumeDecisionInput(**values)  # type: ignore[arg-type]


def test_exact_compatible_live_state_is_fast_resume() -> None:
    decision = decide_resume_route(_input())

    assert decision.route == "FAST_RESUME"
    assert decision.drift == "EXACT"
    assert decision.reason_codes == ("EXACT_LIVE_MATCH",)


def test_explainable_drift_is_reconcile() -> None:
    decision = decide_resume_route(
        _input(
            live_repository_state=McfLiveRepositoryState(
                repository="leon337/project",
                branch="feat/r5",
                head_sha="b" * 40,
                worktree_clean=True,
            ),
            material_drift_explainable=True,
            drift_reason="EXPLAINABLE_FORWARD_DRIFT",
        )
    )

    assert decision.route == "RECONCILE"
    assert decision.drift == "EXPLAINABLE"
    assert decision.reason_codes == ("EXPLAINABLE_FORWARD_DRIFT",)


def test_unexplained_drift_is_recovery() -> None:
    decision = decide_resume_route(
        _input(
            live_repository_state=McfLiveRepositoryState(
                repository="leon337/project",
                branch="feat/r5",
                head_sha="c" * 40,
                worktree_clean=True,
            )
        )
    )

    assert decision.route == "RECOVER_MCF_PROJECT"
    assert decision.drift == "UNEXPLAINED"
    assert decision.reason_codes == ("UNEXPLAINED_DIVERGENCE",)


def test_missing_authority_integrity_or_transferability_forces_recovery() -> None:
    cases = (
        ({"checkpoint_available": False}, "CHECKPOINT_ABSENT"),
        ({"live_repository_state": None}, "LIVE_GIT_UNAVAILABLE"),
        ({"authoritative_records_resolved": False}, "AUTHORITATIVE_RECORDS_UNRESOLVED"),
        ({"methodology_pin_valid": False}, "METHODOLOGY_PIN_MISMATCH"),
        ({"checkpoint_integrity_valid": False}, "CHECKPOINT_INTEGRITY_INVALID"),
        ({"transferability": "BLOCKED_LOCAL_ONLY_STATE"}, "CHECKPOINT_NOT_TRANSFERABLE"),
        ({"checkpoint_sha": None}, "CHECKPOINT_SHA_ABSENT"),
    )

    for overrides, expected_reason in cases:
        decision = decide_resume_route(_input(**overrides))
        assert decision.route == "RECOVER_MCF_PROJECT"
        assert expected_reason in decision.reason_codes


def test_repository_identity_mismatch_forces_recovery() -> None:
    decision = decide_resume_route(
        _input(
            live_repository_state=McfLiveRepositoryState(
                repository="other/project",
                branch="feat/r5",
                head_sha="a" * 40,
                worktree_clean=True,
            )
        )
    )

    assert decision.route == "RECOVER_MCF_PROJECT"
    assert decision.drift == "UNEXPLAINED"
    assert decision.reason_codes == ("REPOSITORY_IDENTITY_MISMATCH",)


def test_missing_checkpoint_and_live_state_report_both_failures_in_stable_order() -> None:
    decision = decide_resume_route(
        _input(
            checkpoint_available=False,
            live_repository_state=None,
            authoritative_records_resolved=False,
            methodology_pin_valid=False,
            checkpoint_integrity_valid=False,
            transferability=None,
            checkpoint_sha=None,
        )
    )

    assert decision.route == "RECOVER_MCF_PROJECT"
    assert decision.drift == "UNKNOWN"
    assert decision.reason_codes == (
        "CHECKPOINT_ABSENT",
        "LIVE_GIT_UNAVAILABLE",
        "AUTHORITATIVE_RECORDS_UNRESOLVED",
        "METHODOLOGY_PIN_MISMATCH",
        "CHECKPOINT_INTEGRITY_INVALID",
        "CHECKPOINT_NOT_TRANSFERABLE",
        "CHECKPOINT_SHA_ABSENT",
    )
