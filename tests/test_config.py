from pathlib import Path

from triview_workspace.domain import PanelKind
from triview_workspace.infrastructure import load_workspace_bundle


def test_example_configuration_loads() -> None:
    path = Path("config/workspaces/three-mobile.json")

    workspace, layout = load_workspace_bundle(path)

    assert workspace.layout_id == layout.id
    assert len(workspace.panels) == 3
    assert len(layout.slots) == 3
    assert workspace.panels[0].kind is PanelKind.BROWSER
