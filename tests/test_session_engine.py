from __future__ import annotations

from pathlib import Path

from triview_workspace.domain import (
    LayoutSpec,
    NormalizedRect,
    PanelKind,
    PanelSpec,
    WorkspaceSpec,
)
from triview_workspace.engines import WorkspaceSessionEngine
from triview_workspace.infrastructure import WorkspaceRepository


def sample_engine(tmp_path: Path) -> WorkspaceSessionEngine:
    layout = LayoutSpec(
        id="three",
        name="Três",
        slots=(
            NormalizedRect(0, 0, 0.3, 1),
            NormalizedRect(0.35, 0, 0.3, 1),
            NormalizedRect(0.7, 0, 0.3, 1),
        ),
    )
    workspace = WorkspaceSpec(
        id="default",
        name="Padrão",
        layout_id=layout.id,
        panels=(PanelSpec("web", "Web", PanelKind.BROWSER, "https://example.com"),),
    )
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    catalog = repository.load_or_bootstrap(workspace, layout)
    return WorkspaceSessionEngine(repository, catalog)


def test_session_engine_duplicates_renames_and_restores_active(tmp_path: Path) -> None:
    engine = sample_engine(tmp_path)

    duplicated, _ = engine.duplicate_current("Pesquisa")
    assert duplicated.id == "pesquisa"
    assert engine.catalog.active_workspace_id == "pesquisa"

    renamed, _ = engine.rename_current("Pesquisa técnica")
    assert renamed.name == "Pesquisa técnica"

    reopened = WorkspaceSessionEngine(engine.repository, engine.repository.load())
    assert reopened.current_workspace.id == "pesquisa"
    assert reopened.current_workspace.name == "Pesquisa técnica"


def test_session_engine_updates_panels_and_deletes_current(tmp_path: Path) -> None:
    engine = sample_engine(tmp_path)
    engine.duplicate_current("Segundo")

    panels = (
        PanelSpec("docs", "Documentação", PanelKind.BROWSER, "https://docs.python.org"),
        PanelSpec("terminal", "Terminal", PanelKind.APPLICATION, "x-terminal-emulator"),
    )
    workspace, _ = engine.update_panels(panels)
    assert workspace.panels == panels

    workspace, _ = engine.delete_current()
    assert workspace.id == "default"
    assert engine.repository.load().active_workspace_id == "default"
