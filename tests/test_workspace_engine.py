from triview_workspace.domain import (
    LayoutSpec,
    NormalizedRect,
    PanelKind,
    PanelSpec,
    WorkspaceSpec,
)
from triview_workspace.engines import (
    LayoutEngine,
    PanelRegistry,
    PlaceholderPanelAdapter,
    WorkspaceEngine,
)


def test_workspace_supports_browser_and_application_panels() -> None:
    layout = LayoutSpec(
        id="two",
        name="Two",
        slots=(
            NormalizedRect(0.0, 0.0, 0.5, 1.0),
            NormalizedRect(0.5, 0.0, 0.5, 1.0),
        ),
    )
    workspace = WorkspaceSpec(
        id="demo",
        name="Demo",
        layout_id="two",
        panels=(
            PanelSpec("web", "Web", PanelKind.BROWSER, "https://example.com"),
            PanelSpec("app", "App", PanelKind.APPLICATION, "x-terminal-emulator"),
        ),
    )
    registry = PanelRegistry()
    registry.register(PlaceholderPanelAdapter())

    prepared = WorkspaceEngine(LayoutEngine(), registry).prepare(
        workspace,
        layout,
        viewport_width=1200,
        viewport_height=700,
    )

    assert [item.panel.kind for item in prepared] == [
        PanelKind.BROWSER,
        PanelKind.APPLICATION,
    ]
    assert all(item.adapter_name == "placeholder" for item in prepared)


def test_workspace_rejects_more_panels_than_slots() -> None:
    layout = LayoutSpec(
        id="one",
        name="One",
        slots=(NormalizedRect(0, 0, 1, 1),),
    )
    workspace = WorkspaceSpec(
        id="invalid",
        name="Invalid",
        layout_id="one",
        panels=(
            PanelSpec("one", "One", PanelKind.BROWSER, "https://one.example"),
            PanelSpec("two", "Two", PanelKind.BROWSER, "https://two.example"),
        ),
    )
    registry = PanelRegistry()
    registry.register(PlaceholderPanelAdapter())

    try:
        WorkspaceEngine(LayoutEngine(), registry).prepare(workspace, layout, 800, 600)
    except ValueError as error:
        assert "more panels" in str(error)
    else:
        raise AssertionError("Expected ValueError")
