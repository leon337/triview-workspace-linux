"""Compatibility entry point for the complete TriView desktop shell."""

from __future__ import annotations

import logging

import triview_workspace.gui_rc4_atomic as _atomic_gui
from triview_workspace.engines.browser_xephyr_managed import (
    ManagedXephyrEmbeddedBraveBrowserBackend,
)
from triview_workspace.runtime_observability import record_runtime_event

# Keep the long-lived atomic entry point while replacing its runtime factory
# with host-tree-aware Xephyr discovery before any WorkspaceWindow is created.
_atomic_gui.XephyrEmbeddedBraveBrowserBackend = (
    ManagedXephyrEmbeddedBraveBrowserBackend
)

_AtomicWorkspaceWindow = _atomic_gui.WorkspaceWindow


class WorkspaceWindow(_AtomicWorkspaceWindow):
    """Finalize the original Session Engine before the hardened RC4 shutdown."""

    def _close(self) -> None:
        if not self._closed:
            recovery_engine = getattr(self, "recovery_engine", None)
            if recovery_engine is not None:
                try:
                    statuses = self._runtime_statuses()
                    recovery_engine.finish(self.workspace, statuses)
                    record_runtime_event(
                        "session_clean_shutdown_recorded",
                        workspace_id=self.workspace.id,
                        open_panel_ids=sorted(statuses),
                    )
                except Exception as exc:  # noqa: BLE001
                    logging.exception("Unable to record clean operational shutdown")
                    record_runtime_event(
                        "session_clean_shutdown_failed",
                        workspace_id=getattr(getattr(self, "workspace", None), "id", None),
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
        super()._close()


# gui_rc4_atomic.main resolves this module global at call time. Replacing it here
# preserves the approved main routine and runtime while adding the missing hook.
_atomic_gui.WorkspaceWindow = WorkspaceWindow

APP_TITLE = _atomic_gui.APP_TITLE
DEFAULT_WORKSPACE = _atomic_gui.DEFAULT_WORKSPACE
PanelCard = _atomic_gui.PanelCard
PanelEditorDialog = _atomic_gui.PanelEditorDialog
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
