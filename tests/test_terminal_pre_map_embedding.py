from __future__ import annotations

from typing import Any

from triview_workspace.engines.terminal_embedded import EmbeddedFirstX11PanelRuntimeBackend


class _FakeProcess:
    pid = 4321

    @staticmethod
    def poll() -> None:
        return None


def test_terminal_candidate_search_includes_unmapped_windows(monkeypatch: Any) -> None:
    runtime = EmbeddedFirstX11PanelRuntimeBackend()
    calls: list[tuple[str, str, bool]] = []

    def search(
        _xdotool: str,
        selector: str,
        value: str,
        *,
        only_visible: bool = True,
    ) -> list[str]:
        calls.append((selector, value, only_visible))
        return ["77"] if selector == "--pid" else []

    monkeypatch.setattr(runtime, "_search_windows", search)
    monkeypatch.setattr(runtime, "_window_pid", lambda *_args: 4321)

    result = runtime._candidate_window_ids("xdotool", {4321}, ("Terminal",), set())

    assert result == ["77"]
    assert calls
    assert all(only_visible is False for _selector, _value, only_visible in calls)


def test_terminal_is_staged_without_waiting_until_viewable(monkeypatch: Any) -> None:
    runtime = EmbeddedFirstX11PanelRuntimeBackend()
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(runtime, "_process_family", lambda _pid: {4321})
    monkeypatch.setattr(
        runtime,
        "_candidate_window_ids",
        lambda *_args, **_kwargs: ["77"],
    )
    monkeypatch.setattr(
        runtime,
        "_window_is_viewable",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not wait for MapState")),
    )
    monkeypatch.setattr(
        runtime,
        "_run_xdotool",
        lambda _xdotool, *args: calls.append(tuple(args)),
    )

    result = runtime._wait_for_window(
        "xdotool",
        "xwininfo",
        _FakeProcess(),  # type: ignore[arg-type]
        ("TriView Terminal",),
        set(),
    )

    assert result == "77"
    assert calls == [
        ("windowmove", "77", "-32000", "-32000"),
        ("windowunmap", "77"),
    ]
