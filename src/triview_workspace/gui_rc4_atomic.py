"""Compatibility entry point for the LEA-247 live-workspace RC4 runtime.

The public module name is preserved so existing launchers and regression tests
keep one stable import path while the implementation lives in ``gui_rc4_live``.
"""

from triview_workspace.gui_rc4_live import (
    APP_TITLE,
    BROWSER_BACKEND_NAME,
    DEFAULT_WORKSPACE,
    EMERGENCY_SHORTCUTS,
    LIVE_BROWSER_BACKEND_NAME,
    POPUP_FAILSAFE_MS,
    POPUP_WATCH_INTERVAL_MS,
    PanelCard,
    PanelEditorDialog,
    THREE_GPT_WORKSPACE,
    WorkspaceViewState,
    WorkspaceWindow,
    deferred_menu_action,
    global_bar_height,
    main,
    panel_header_height,
    parse_work_area,
    proportional_panel_bounds,
    release_menu_grab,
    request_managed_maximize,
    runtime_panel_id,
    safe_popup_menu,
    workspace_panel_signature,
)

__all__ = [
    "APP_TITLE",
    "BROWSER_BACKEND_NAME",
    "DEFAULT_WORKSPACE",
    "EMERGENCY_SHORTCUTS",
    "LIVE_BROWSER_BACKEND_NAME",
    "POPUP_FAILSAFE_MS",
    "POPUP_WATCH_INTERVAL_MS",
    "PanelCard",
    "PanelEditorDialog",
    "THREE_GPT_WORKSPACE",
    "WorkspaceViewState",
    "WorkspaceWindow",
    "deferred_menu_action",
    "global_bar_height",
    "main",
    "panel_header_height",
    "parse_work_area",
    "proportional_panel_bounds",
    "release_menu_grab",
    "request_managed_maximize",
    "runtime_panel_id",
    "safe_popup_menu",
    "workspace_panel_signature",
]


if __name__ == "__main__":
    raise SystemExit(main())
