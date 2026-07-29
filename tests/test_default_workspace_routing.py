from __future__ import annotations

from pathlib import Path

from triview_workspace.domain import PanelKind
from triview_workspace.engines import (
    ApplicationPanelAdapter,
    BrowserPanelAdapter,
    PanelRegistry,
    TerminalPanelAdapter,
)
from triview_workspace.infrastructure import load_workspace_bundle


DEFAULT_WORKSPACE = Path("config/workspaces/three-mobile.json")


def test_default_terminal_panel_uses_terminal_kind_and_shell_target() -> None:
    workspace, _layout = load_workspace_bundle(DEFAULT_WORKSPACE)
    panel = next(item for item in workspace.panels if item.id == "terminal")

    assert panel.title == "Terminal"
    assert panel.kind is PanelKind.TERMINAL
    assert panel.target == "bash -l"


def test_default_terminal_panel_routes_to_terminal_adapter() -> None:
    workspace, _layout = load_workspace_bundle(DEFAULT_WORKSPACE)
    panel = next(item for item in workspace.panels if item.id == "terminal")
    registry = PanelRegistry()
    for adapter in (
        BrowserPanelAdapter(),
        ApplicationPanelAdapter(),
        TerminalPanelAdapter(),
    ):
        registry.register(adapter)

    adapter = registry.resolve(panel.kind)

    assert adapter.name == "terminal"
    assert adapter.build_launch_request(panel)["mode"] == "terminal"
