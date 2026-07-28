from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from triview_workspace.catalog_migrations import (
    THREE_GPT_WORKSPACE_ID,
    ensure_three_gpt_workspace,
)
from triview_workspace.domain import PanelKind
from triview_workspace.engines.browser import (
    BrowserBackendAvailability,
    BrowserEngine,
    BrowserLaunchRequest,
    BrowserSession,
)
from triview_workspace.infrastructure import WorkspaceRepository, load_workspace_bundle

DEVELOPMENT_WORKSPACE = Path("config/workspaces/three-mobile.json")
THREE_GPT_WORKSPACE = Path("config/workspaces/three-gpt-agents.json")


class CapturingBrowserBackend:
    def __init__(self) -> None:
        self.requests: list[BrowserLaunchRequest] = []

    def availability(self) -> BrowserBackendAvailability:
        return BrowserBackendAvailability(True, "ok", "brave", "xdotool")

    def launch(self, request: BrowserLaunchRequest, parent_window_id: int) -> BrowserSession:
        self.requests.append(request)
        return BrowserSession(request.panel_id, request.url, None, str(parent_window_id), True)

    def resize(self, session: BrowserSession, width: int, height: int) -> None:
        return None

    def close(self, session: BrowserSession) -> None:
        return None


def test_canonical_three_agent_bundle_has_three_isolated_browser_panels() -> None:
    workspace, layout = load_workspace_bundle(THREE_GPT_WORKSPACE)

    assert workspace.id == THREE_GPT_WORKSPACE_ID
    assert workspace.name == "Três Agentes GPT"
    assert workspace.layout_id == layout.id
    assert len(layout.slots) == 3
    assert len(workspace.panels) == 3
    assert len({panel.id for panel in workspace.panels}) == 3
    assert all(panel.kind is PanelKind.BROWSER for panel in workspace.panels)
    assert all(panel.target == "https://chatgpt.com" for panel in workspace.panels)


def test_three_agent_panel_ids_generate_distinct_browser_profiles(tmp_path: Path) -> None:
    workspace, _layout = load_workspace_bundle(THREE_GPT_WORKSPACE)
    backend = CapturingBrowserBackend()
    engine = BrowserEngine(backend, profile_root=tmp_path / "profiles")

    for index, panel in enumerate(workspace.panels, start=1):
        engine.open(panel.id, panel.target, index, 420, 700)

    assert [request.panel_id for request in backend.requests] == [
        "agent-gpt-1",
        "agent-gpt-2",
        "agent-gpt-3",
    ]
    assert len({request.profile_dir for request in backend.requests}) == 3
    assert all(request.profile_dir.parent == tmp_path / "profiles" for request in backend.requests)


def test_three_agent_workspace_is_added_and_selected_for_technical_only_catalog(
    tmp_path: Path,
) -> None:
    development, development_layout = load_workspace_bundle(DEVELOPMENT_WORKSPACE)
    canonical, canonical_layout = load_workspace_bundle(THREE_GPT_WORKSPACE)
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    catalog = repository.load_or_bootstrap(development, development_layout)

    updated, added, activated = ensure_three_gpt_workspace(
        repository,
        catalog,
        canonical,
        canonical_layout,
    )

    assert added is True
    assert activated is True
    assert updated.active_workspace_id == THREE_GPT_WORKSPACE_ID
    assert updated.workspace_by_id("development-demo") == development
    assert updated.workspace_by_id(THREE_GPT_WORKSPACE_ID) == canonical
    assert repository.load() == updated


def test_existing_three_agent_workspace_preserves_edited_agent_titles(tmp_path: Path) -> None:
    development, development_layout = load_workspace_bundle(DEVELOPMENT_WORKSPACE)
    canonical, canonical_layout = load_workspace_bundle(THREE_GPT_WORKSPACE)
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    catalog = repository.load_or_bootstrap(development, development_layout)
    catalog, _added, _activated = ensure_three_gpt_workspace(
        repository,
        catalog,
        canonical,
        canonical_layout,
    )
    edited = replace(
        canonical,
        panels=(
            replace(canonical.panels[0], title="Arquiteto"),
            replace(canonical.panels[1], title="Implementador"),
            replace(canonical.panels[2], title="Revisor"),
        ),
    )
    catalog = repository.save_workspace(catalog, edited, make_active=True)

    repeated, added, activated = ensure_three_gpt_workspace(
        repository,
        catalog,
        canonical,
        canonical_layout,
    )

    assert added is False
    assert activated is False
    assert repeated == catalog
    assert [panel.title for panel in repeated.workspace_by_id(THREE_GPT_WORKSPACE_ID).panels] == [
        "Arquiteto",
        "Implementador",
        "Revisor",
    ]


def test_custom_active_workspace_is_not_replaced_by_canonical_workspace(tmp_path: Path) -> None:
    development, development_layout = load_workspace_bundle(DEVELOPMENT_WORKSPACE)
    canonical, canonical_layout = load_workspace_bundle(THREE_GPT_WORKSPACE)
    repository = WorkspaceRepository(tmp_path / "workspaces.json")
    catalog = repository.load_or_bootstrap(development, development_layout)
    custom = replace(development, id="custom-workspace", name="Meu workspace")
    catalog = repository.save_workspace(catalog, custom, make_active=True)

    updated, added, activated = ensure_three_gpt_workspace(
        repository,
        catalog,
        canonical,
        canonical_layout,
    )

    assert added is True
    assert activated is False
    assert updated.active_workspace_id == "custom-workspace"
    assert updated.workspace_by_id(THREE_GPT_WORKSPACE_ID) == canonical
