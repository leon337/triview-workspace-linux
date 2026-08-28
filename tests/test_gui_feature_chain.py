from __future__ import annotations

from types import SimpleNamespace

import triview_workspace.gui as public_gui
import triview_workspace.gui_hub as gui_hub
import triview_workspace.gui_rc4_atomic as atomic_gui
import triview_workspace.gui_sessions as gui_sessions


def test_public_gui_preserves_atomic_main_identity_and_feature_layers() -> None:
    chain = public_gui.WorkspaceWindow.mro()

    assert public_gui.main is atomic_gui.main
    assert atomic_gui.WorkspaceWindow is public_gui.WorkspaceWindow
    assert gui_hub.WorkspaceWindow in chain
    assert gui_sessions.WorkspaceWindow in chain
    assert chain.index(gui_hub.WorkspaceWindow) < chain.index(gui_sessions.WorkspaceWindow)


def test_workspace_hub_action_remains_registered_in_complete_shell(monkeypatch) -> None:
    registered: list[tuple[str, str, int]] = []
    parent = gui_hub.WorkspaceWindow.__mro__[1]
    monkeypatch.setattr(parent, "__init__", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        gui_hub.WorkspaceWindow,
        "register_header_action",
        lambda _self, action_id, label, _command, *, order: registered.append(
            (action_id, label, order)
        ),
    )
    monkeypatch.setattr(
        gui_hub.WorkspaceWindow,
        "set_product_stage",
        lambda *_args, **_kwargs: None,
    )

    window = object.__new__(gui_hub.WorkspaceWindow)
    window.status_text = SimpleNamespace(set=lambda _value: None)
    gui_hub.WorkspaceWindow.__init__(
        window,
        root=object(),
        repository=object(),
        session_engine=object(),
        hub_repository=object(),
    )

    assert registered == [("workspace-hub", "Workspace Hub", 10)]
