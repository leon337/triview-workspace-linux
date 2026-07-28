from __future__ import annotations

import inspect
from pathlib import Path

import triview_workspace.gui as active_gui
import triview_workspace.gui_rc4_atomic as atomic_gui
from triview_workspace.diagnostic_blackbox_rc import ByteSafeBlackboxCollector
from triview_workspace.diagnostic_blackbox_verified import VerifiedBlackboxCollector
from triview_workspace.engines.browser_live_rc import (
    HARDENED_BROWSER_BACKEND_NAME,
    ImmediateHideXfwm4FinalClientX11BraveBrowserBackend,
)


def test_active_entry_uses_hardened_release_candidate_runtime() -> None:
    assert active_gui.main is atomic_gui.main
    assert active_gui.WorkspaceWindow is atomic_gui.WorkspaceWindow
    assert atomic_gui.RC_BROWSER_BACKEND_NAME == HARDENED_BROWSER_BACKEND_NAME
    assert atomic_gui.RC_BROWSER_BACKEND_NAME == (
        "ImmediateHideXfwm4FinalClientX11BraveBrowserBackend"
    )


def test_workspace_switch_increments_generation_without_closing_runtimes() -> None:
    source = inspect.getsource(atomic_gui.WorkspaceWindow._load_workspace_view)

    assert "self._generation += 1" in source
    assert "close_all" not in source
    assert "super()._load_workspace_view" in source


def test_release_candidate_does_not_enable_focus_follows_mouse() -> None:
    source = inspect.getsource(atomic_gui.WorkspaceWindow._poll_browser_pointer_focus)

    assert "root.after" not in source
    assert "focus_under_pointer" not in source
    assert "return" in source


def test_every_new_browser_candidate_is_hidden_before_final_selection() -> None:
    source = inspect.getsource(
        ImmediateHideXfwm4FinalClientX11BraveBrowserBackend._wait_for_unique_window
    )

    assert source.index("_hide_and_stage_window") < source.index(
        "is_final_browser_candidate"
    )
    assert "browser_candidate_forced_hidden" in source
    assert "visible_before_hide" in source


def test_runtime_event_tailer_uses_binary_offsets_and_partial_line_buffer() -> None:
    source = inspect.getsource(ByteSafeBlackboxCollector._runtime_event_loop)

    assert 'open("rb")' in source
    assert "pending + chunk" in source
    assert 'split(b"\\n")' in source
    assert "handle.seek(offset)" in source


def test_candidate_diagnostic_uses_verified_byte_safe_collector() -> None:
    script = Path("scripts/candidate-diagnose.sh").read_text(encoding="utf-8")

    assert issubclass(VerifiedBlackboxCollector, ByteSafeBlackboxCollector)
    assert "triview_workspace.diagnostic_blackbox_verified" in script
    assert "--auto-launch" in script
    assert "--auto-stop-on-application-exit" in script
