"""Compatibility entry point for the complete TriView desktop shell."""

from __future__ import annotations

import logging
from pathlib import Path

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


def _record_shutdown_event(event: str, **fields: object) -> None:
    """Never let diagnostics prevent the desktop from releasing its resources."""

    try:
        record_runtime_event(event, **fields)
    except Exception:  # noqa: BLE001
        logging.exception("Unable to write shutdown observability event %s", event)


class WorkspaceWindow(_AtomicWorkspaceWindow):
    """Finalize the original Session Engine before the hardened RC4 shutdown."""

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
                        workspace_id=getattr(getattr(self, "workspace", None), "id", None),
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                else:
                    _record_shutdown_event(
                        "session_clean_shutdown_recorded",
                        workspace_id=self.workspace.id,
                        open_panel_ids=sorted(statuses),
                    )
        super()._close()


def main(
    workspace_path: Path | None = None,
    data_file: Path | None = None,
) -> int:
    """Run the approved atomic main with the clean-shutdown wrapper installed."""

    previous_window = _atomic_gui.WorkspaceWindow
    _atomic_gui.WorkspaceWindow = WorkspaceWindow
    try:
        return _atomic_gui.main(workspace_path, data_file)
    finally:
        _atomic_gui.WorkspaceWindow = previous_window


APP_TITLE = _atomic_gui.APP_TITLE
DEFAULT_WORKSPACE = _atomic_gui.DEFAULT_WORKSPACE
PanelCard = _atomic_gui.PanelCard
PanelEditorDialog = _atomic_gui.PanelEditorDialog

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
