from __future__ import annotations

from typing import Any

import triview_workspace.gui as public_gui
import triview_workspace.gui_hub as gui_hub
import triview_workspace.gui_rc4_atomic as atomic_gui
from triview_workspace.gui_hub_responsive import (
    HUB_ACTION_LABELS,
    ResponsiveWorkspaceHubDialog,
    find_hub_action_frame,
    reserve_hub_action_bar,
    responsive_hub_geometry,
)


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


def test_public_entry_installs_responsive_hub_without_replacing_atomic_main() -> None:
    assert gui_hub.WorkspaceHubDialog is ResponsiveWorkspaceHubDialog
    assert public_gui.main is atomic_gui.main
