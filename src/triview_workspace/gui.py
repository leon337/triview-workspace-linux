"""Compatibility entry point for the complete TriView desktop shell."""

from __future__ import annotations

import logging

import triview_workspace.gui_hub as _hub_gui
import triview_workspace.gui_rc4_atomic as _atomic_gui
from triview_workspace.engines.browser_xephyr_managed import (
    ManagedXephyrEmbeddedBraveBrowserBackend,
)
from triview_workspace.gui_hub_responsive import ResponsiveWorkspaceHubDialog
from triview_workspace.runtime_observability import record_runtime_event

# Keep the long-lived atomic entry point while replacing its runtime factory
# with host-tree-aware Xephyr discovery before any WorkspaceWindow is created.
_atomic_gui.XephyrEmbeddedBraveBrowserBackend = (
    ManagedXephyrEmbeddedBraveBrowserBackend
)

# gui_hub.WorkspaceWindow resolves this module global when the user opens the Hub.
# Replace only the dialog implementation; the Hub repository and window chain remain intact.
_hub_gui.WorkspaceHubDialog = ResponsiveWorkspaceHubDialog


def _record_shutdown_event(event: str, **fields: object) -> None:
    """Never let diagnostics prevent the desktop from releasing its resources."""

    try:
        record_runtime_event(event, **fields)
    except Exception:  # noqa: BLE001
        logging.exception("Unable to write shutdown observability event %s", event)


_existing_window = _atomic_gui.WorkspaceWindow
if getattr(_existing_window, "_triview_clean_shutdown_hook", False):
    WorkspaceWindow = _existing_window
else:

    class WorkspaceWindow(_existing_window):
        """Finalize the original Session Engine before the hardened RC4 shutdown."""

        _triview_clean_shutdown_hook = True

        def _close(self) -> None:
            if not self._closed:
                recovery_engine = getattr(self, "recovery_engine", None)
                if recovery_engine is not None:
                    try:
                        statuses = self._runtime_statuses()
                        recovery_engine.finish(self.workspace, statuses)
                    except Exception as exc:  # noqa: BLE001
                        logging.exception("Unable to record clean operational shutdown")
                        _record_shutdown_event(
                            "session_clean_shutdown_failed",
                            workspace_id=getattr(
                                getattr(self, "workspace", None), "id", None
                            ),
                            error_type=type(exc).__name__,
                            error=str(exc),
                        )
                    else:
                        _record_shutdown_event(
                            "session_clean_shutdown_recorded",
                            workspace_id=self.workspace.id,
                            open_panel_ids=sorted(statuses),
                        )

                # Preserve the explicit RC4 bridge lifecycle contract in the
                # effective atomic class inspected and executed by the gates.
                bridge = getattr(self, "_wheel_bridge", None)
                if bridge is not None:
                    bridge.close()
                    self._wheel_bridge = None
            super()._close()

    # The approved atomic main resolves WorkspaceWindow from its own module.
    # The marker above makes this replacement idempotent across module reloads.
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
