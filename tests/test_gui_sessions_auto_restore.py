from __future__ import annotations

import pytest

from triview_workspace.gui_sessions import auto_restore_enabled


def test_auto_restore_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRIVIEW_AUTO_RESTORE", raising=False)
    assert auto_restore_enabled() is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_auto_restore_accepts_explicit_truthy_values(value: str) -> None:
    assert auto_restore_enabled({"TRIVIEW_AUTO_RESTORE": value}) is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "unexpected"])
def test_auto_restore_fails_closed_for_other_values(value: str) -> None:
    assert auto_restore_enabled({"TRIVIEW_AUTO_RESTORE": value}) is False
