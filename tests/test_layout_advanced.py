from __future__ import annotations

from pathlib import Path

import pytest

from triview_workspace.domain import (
    LayoutSpec,
    NormalizedRect,
    PanelKind,
    PanelSpec,
    Viewport,
    WorkspaceSpec,
)
from triview_workspace.engines import ResponsiveLayoutEngine
from triview_workspace.engines.layout_advanced import (
    LayoutValidationError,
    build_preset_layout,
    create_layout,
    preset_slots,
)
from triview_workspace.engines.session import WorkspaceSessionEngine
from triview_workspace.infrastructure import WorkspaceRepository


def test_layout_validation_rejects_overlap_and_out_of_bounds() -> None:
    with pytest.raises(LayoutValidationError, match="sobrepõem"):
        create_layout(
            "overlap-layout",
            "Overlap",
            (
                NormalizedRect(0, 0, 0.7, 1),
                NormalizedRect(0.6, 0, 0.4, 1),
            ),
        )
    with pytest.raises(ValueError, match="fit inside the viewport"):
        NormalizedRect(0.8, 0, 0.3, 1)


def test_presets_cover_columns_stack_grid_and_focus() -> None:
    assert len(preset_slots("columns", 3)) == 3
    assert preset_slots("stack", 2)[1].y == 0.5
    assert preset_slots("grid", 4)[3].x == 0.5
    assert preset_slots("focus-left", 3)[0].width == 0.68
    assert preset_slots("two-plus-one", 3)[2].width == 1


def test_responsive_engine_uses_stack_on_narrow_viewport() -> None:
    layout = build_preset_layout("columns", 3, "three-columns", "Three columns")
    bounds = ResponsiveLayoutEngine().arrange(layout, Viewport(600, 900))
    assert bounds[0].width == 600
    assert [item.y for item in bounds] == [0, 300, 600]
    assert [item.height for item in bounds] == [300, 300, 300]


def test_responsive_engine_uses_two_plus_one_on_medium_viewport() -> None:
    layout = build_preset_layout("columns", 3, "three-columns", "Three columns")
    bounds = ResponsiveLayoutEngine().arrange(layout, Viewport(900, 600))
    assert bounds[0].width == 450
    assert bounds[1].x == 450
    assert bounds[2].width == 900
    assert bounds[2].y == 300


def test_session_engine_saves_and_selects_custom_layout(tmp_path: Path) -> None:
    panels = tuple(
        PanelSpec(f"p{index}", f"Panel {index}", PanelKind.BROWSER, "https://example.com")
        for index in range(3)
    )
    initial_layout = build_preset_layout("columns", 3, "initial-layout", "Initial")
    workspace = WorkspaceSpec("workspace", "Workspace", initial_layout.id, panels)
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    catalog = repository.load_or_bootstrap(workspace, initial_layout)
    session = WorkspaceSessionEngine(repository, catalog)
    custom = build_preset_layout("two-plus-one", 3, "custom-layout", "Custom")

    current_workspace, current_layout = session.save_layout(custom, select=True)

    assert current_workspace.layout_id == "custom-layout"
    assert current_layout == custom
    loaded = repository.load()
    assert loaded.layout_by_id("custom-layout") == custom
    assert loaded.workspace_by_id("workspace").layout_id == "custom-layout"


def test_session_engine_does_not_overwrite_layout_silently(tmp_path: Path) -> None:
    layout = LayoutSpec("single-layout", "Single", (NormalizedRect(0, 0, 1, 1),))
    workspace = WorkspaceSpec(
        "workspace",
        "Workspace",
        layout.id,
        (PanelSpec("p1", "Panel", PanelKind.BROWSER, "https://example.com"),),
    )
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    session = WorkspaceSessionEngine(repository, repository.load_or_bootstrap(workspace, layout))
    with pytest.raises(Exception, match="já existe"):
        session.save_layout(layout)
