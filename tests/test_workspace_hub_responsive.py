from __future__ import annotations

from types import MethodType, SimpleNamespace
from typing import Any

import triview_workspace.gui as public_gui
import triview_workspace.gui_hub as gui_hub
import triview_workspace.gui_hub_responsive as responsive_hub
import triview_workspace.gui_rc4_atomic as atomic_gui
from triview_workspace.gui_hub_responsive import (
    HUB_ACTION_LABELS,
    ResponsiveWorkspaceHubDialog,
    activate_hub_catalog,
    find_hub_action_frame,
    reserve_hub_action_bar,
    responsive_hub_geometry,
)
from triview_workspace.gui_layouts import WorkspaceWindow as LayoutWorkspaceWindow
from triview_workspace.gui_sessions import WorkspaceWindow as SessionWorkspaceWindow


class FakeWidget:
    def __init__(
        self,
        name: str,
        events: list[tuple[str, str, dict[str, Any]]],
        *,
        text: str | None = None,
        children: tuple["FakeWidget", ...] = (),
    ) -> None:
        self.name = name
        self.events = events
        self.text = text
        self.children = children

    def pack_forget(self) -> None:
        self.events.append((self.name, "pack_forget", {}))

    def pack(self, **kwargs: Any) -> None:
        self.events.append((self.name, "pack", kwargs))

    def winfo_children(self) -> tuple["FakeWidget", ...]:
        return self.children

    def cget(self, option: str) -> str:
        if option != "text" or self.text is None:
            raise AttributeError(option)
        return self.text


class FakeSessionEngine:
    def __init__(self, catalog: Any) -> None:
        self.catalog = catalog

    @property
    def current_workspace(self) -> Any:
        return self.catalog.workspace

    @property
    def current_layout(self) -> Any:
        return self.catalog.layout


class FakeRecoveryEngine:
    def __init__(self, events: list[tuple[Any, ...]]) -> None:
        self.events = events

    def begin(self, workspace: Any) -> None:
        self.events.append(("begin", workspace.id))


class FakeStatus:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def test_geometry_fits_1366_by_768_linux_desktop() -> None:
    assert responsive_hub_geometry(1366, 768) == (940, 600)
    assert responsive_hub_geometry(800, 600) == (736, 490)


def test_fixed_action_bar_is_reserved_before_expandable_content() -> None:
    events: list[tuple[str, str, dict[str, Any]]] = []
    content = FakeWidget("content", events)
    actions = FakeWidget("actions", events)

    reserve_hub_action_bar(content, actions)

    assert events == [
        ("content", "pack_forget", {}),
        ("actions", "pack_forget", {}),
        (
            "actions",
            "pack",
            {"side": "bottom", "fill": "x", "padx": 16, "pady": (8, 16)},
        ),
        (
            "content",
            "pack",
            {"fill": "both", "expand": True, "padx": 16},
        ),
    ]


def test_action_frame_is_found_by_complete_button_contract() -> None:
    events: list[tuple[str, str, dict[str, Any]]] = []
    unrelated = FakeWidget(
        "unrelated",
        events,
        children=(FakeWidget("other", events, text="Outro"),),
    )
    action_buttons = tuple(
        FakeWidget(f"button-{index}", events, text=label)
        for index, label in enumerate(sorted(HUB_ACTION_LABELS))
    )
    actions = FakeWidget("actions", events, children=action_buttons)
    shell = FakeWidget("shell", events, children=(unrelated, actions))

    assert find_hub_action_frame(shell) is actions


def test_hub_catalog_checkpoints_old_workspace_before_rendering_new_one(
    monkeypatch: Any,
) -> None:
    events: list[tuple[Any, ...]] = []
    old_workspace = SimpleNamespace(id="development")
    old_layout = SimpleNamespace(id="three-panels")
    new_workspace = SimpleNamespace(id="imported-workspace")
    new_layout = SimpleNamespace(id="imported-layout")
    old_catalog = SimpleNamespace(workspace=old_workspace, layout=old_layout)
    new_catalog = SimpleNamespace(workspace=new_workspace, layout=new_layout)

    window = object.__new__(SessionWorkspaceWindow)
    window.workspace = old_workspace
    window.layout = old_layout
    window.session_engine = FakeSessionEngine(old_catalog)
    window.recovery_engine = FakeRecoveryEngine(events)
    window._runtime_signature = None
    window._sync_runtime_state = MethodType(
        lambda self, *, force=False: events.append(
            ("sync", self.workspace.id, self.layout.id, force)
        ),
        window,
    )
    window._signature = MethodType(
        lambda self, statuses: (self.workspace.id, tuple(statuses)),
        window,
    )

    def lower_reload(self: Any, message: str) -> None:
        events.append(("render", self.workspace.id, self.layout.id, message))

    monkeypatch.setattr(LayoutWorkspaceWindow, "_load_workspace_view", lower_reload)

    activate_hub_catalog(window, new_catalog, "Workspace criado pelo Hub")

    assert events == [
        ("sync", "development", "three-panels", True),
        (
            "render",
            "imported-workspace",
            "imported-layout",
            "Workspace criado pelo Hub",
        ),
        ("begin", "imported-workspace"),
    ]
    assert window.session_engine.catalog is new_catalog
    assert window.workspace is new_workspace
    assert window.layout is new_layout
    assert window._runtime_signature == ("imported-workspace", ())


def test_use_selected_persists_and_activates_created_workspace(monkeypatch: Any) -> None:
    existing_workspace = SimpleNamespace(id="development")
    existing_layout = SimpleNamespace(id="three-panels")
    created_workspace = SimpleNamespace(id="imported-workspace", name="Workspace Final")
    created_layout = SimpleNamespace(id="imported-layout")
    catalog = SimpleNamespace(
        workspaces=(existing_workspace,),
        layouts=(existing_layout,),
    )
    persisted_catalog = SimpleNamespace(
        workspaces=(existing_workspace, created_workspace),
        layouts=(existing_layout, created_layout),
    )
    entry = SimpleNamespace(id="template-imported", name="Template Importado")
    calls: list[tuple[Any, ...]] = []

    class Hub:
        def instantiate(self, entry_id: str, name: str, **kwargs: Any) -> tuple[Any, Any]:
            calls.append(("instantiate", entry_id, name, kwargs))
            return created_workspace, created_layout

    class Repository:
        def save_workspace(self, source: Any, workspace: Any, layout: Any, **kwargs: Any) -> Any:
            calls.append(("save", source, workspace, layout, kwargs))
            return persisted_catalog

    dialog = object.__new__(ResponsiveWorkspaceHubDialog)
    dialog.top = object()
    dialog.window = SimpleNamespace(
        session_engine=SimpleNamespace(catalog=catalog),
        repository=Repository(),
    )
    dialog.hub = Hub()
    dialog.status = FakeStatus()
    dialog.selected = lambda: entry
    dialog._error = lambda error: calls.append(("error", str(error)))

    monkeypatch.setattr(responsive_hub.simpledialog, "askstring", lambda *a, **k: "Workspace Final")
    monkeypatch.setattr(
        responsive_hub,
        "activate_hub_catalog",
        lambda window, activated_catalog, message: calls.append(
            ("activate", window, activated_catalog, message)
        ),
    )

    dialog.use_selected()

    assert calls[0][0:3] == ("instantiate", "template-imported", "Workspace Final")
    assert calls[0][3] == {
        "existing_workspace_ids": {"development"},
        "existing_layout_ids": {"three-panels"},
    }
    assert calls[1] == (
        "save",
        catalog,
        created_workspace,
        created_layout,
        {"make_active": True},
    )
    assert calls[2] == (
        "activate",
        dialog.window,
        persisted_catalog,
        "Workspace criado pelo Hub",
    )
    assert dialog.status.value == "Workspace Final criado e ativado"


def test_public_entry_installs_responsive_hub_without_replacing_atomic_main() -> None:
    assert gui_hub.WorkspaceHubDialog is ResponsiveWorkspaceHubDialog
    assert public_gui.main is atomic_gui.main
