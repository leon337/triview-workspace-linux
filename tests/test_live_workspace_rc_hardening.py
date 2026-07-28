from __future__ import annotations

import inspect
from pathlib import Path

import triview_workspace.gui as active_gui
import triview_workspace.gui_rc4_atomic as atomic_gui
from triview_workspace.diagnostic_blackbox_rc import ByteSafeBlackboxCollector
from triview_workspace.diagnostic_blackbox_xephyr import XephyrVerifiedBlackboxCollector
from triview_workspace.engines.browser_xephyr import (
    XEPHYR_BROWSER_BACKEND_NAME,
    XephyrEmbeddedBraveBrowserBackend,
)


def test_active_entry_keeps_atomic_contract_with_nested_xephyr_runtime() -> None:
    assert active_gui.main is atomic_gui.main
    assert active_gui.WorkspaceWindow is atomic_gui.WorkspaceWindow
    assert atomic_gui.RC_BROWSER_BACKEND_NAME == XEPHYR_BROWSER_BACKEND_NAME
    assert atomic_gui.RC_BROWSER_BACKEND_NAME == "XephyrEmbeddedBraveBrowserBackend"


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


def test_browser_is_launched_inside_xephyr_parent_before_first_map() -> None:
    launch_source = inspect.getsource(XephyrEmbeddedBraveBrowserBackend.launch)

    assert '"-parent"' in launch_source
    assert "parent_window_id" in launch_source
    assert "self._wait_for_display" in launch_source
    assert launch_source.index("self._wait_for_display") < launch_source.index(
        "browser_process = subprocess.Popen"
    )
    assert 'containment="nested_xephyr"' in launch_source
    assert "external_root_mapping_possible=False" in launch_source
    assert "browser_candidate_forced_hidden" not in launch_source


def test_runtime_event_tailer_uses_binary_offsets_and_partial_line_buffer() -> None:
    source = inspect.getsource(ByteSafeBlackboxCollector._runtime_event_loop)

    assert 'open("rb")' in source
    assert "pending + chunk" in source
    assert 'split(b"\\n")' in source
    assert "handle.seek(offset)" in source


def test_candidate_diagnostic_uses_xephyr_verified_byte_safe_collector() -> None:
    script = Path("scripts/candidate-diagnose.sh").read_text(encoding="utf-8")

    assert issubclass(XephyrVerifiedBlackboxCollector, ByteSafeBlackboxCollector)
    assert "triview_workspace.diagnostic_blackbox_xephyr" in script
    assert "triview_workspace.diagnostic_blackbox_verified" in script
    assert "--auto-launch" in script
    assert "--auto-stop-on-application-exit" in script
