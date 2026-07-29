"""Compatibility entry point for the complete TriView desktop shell."""

import triview_workspace.gui_rc4_atomic as _atomic_gui
from triview_workspace.engines.browser_xephyr_managed import (
    ManagedXephyrEmbeddedBraveBrowserBackend,
)

# Keep the long-lived atomic entry point while replacing its runtime factory
# with host-tree-aware Xephyr discovery before any WorkspaceWindow is created.
_atomic_gui.XephyrEmbeddedBraveBrowserBackend = (
    ManagedXephyrEmbeddedBraveBrowserBackend
)

APP_TITLE = _atomic_gui.APP_TITLE
DEFAULT_WORKSPACE = _atomic_gui.DEFAULT_WORKSPACE
PanelCard = _atomic_gui.PanelCard
PanelEditorDialog = _atomic_gui.PanelEditorDialog
WorkspaceWindow = _atomic_gui.WorkspaceWindow
main = _atomic_gui.main

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
