"""Compatibility entry point for the complete TriView desktop shell."""

import triview_workspace.gui_rc4_atomic as _atomic_gui
import triview_workspace.gui_session as _session_gui
from triview_workspace.engines.browser_xephyr_managed import (
    ManagedXephyrEmbeddedBraveBrowserBackend,
)

# Preserve the approved atomic runtime factory while the public entry point adds
# cross-restart session persistence above it.
_atomic_gui.XephyrEmbeddedBraveBrowserBackend = (
    ManagedXephyrEmbeddedBraveBrowserBackend
)

APP_TITLE = _session_gui.APP_TITLE
DEFAULT_WORKSPACE = _session_gui.DEFAULT_WORKSPACE
PanelCard = _session_gui.PanelCard
PanelEditorDialog = _session_gui.PanelEditorDialog
WorkspaceWindow = _session_gui.WorkspaceWindow
main = _session_gui.main

__all__ = [
    "APP_TITLE",
    "DEFAULT_WORKSPACE",
    "PanelCard",
    "PanelEditorDialog",
    "WorkspaceWindow",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
