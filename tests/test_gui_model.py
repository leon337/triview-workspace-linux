from triview_workspace.domain import PanelKind, PanelSpec, PixelRect, RuntimePanel
from triview_workspace.gui_model import build_panel_view_models, panel_status


def test_panel_status_describes_placeholder_stage() -> None:
    assert "Navegador" in panel_status("browser")
    assert "Aplicação" in panel_status("application")
    assert "adaptador" in panel_status("custom")


def test_runtime_panel_is_converted_for_gui() -> None:
    panel = PanelSpec(
        id="chatgpt",
        title="ChatGPT",
        kind=PanelKind.BROWSER,
        target="https://chatgpt.com",
    )
    runtime = RuntimePanel(
        panel=panel,
        bounds=PixelRect(x=10, y=20, width=300, height=600),
        adapter_name="placeholder",
        launch_request={"mode": "placeholder"},
    )

    result = build_panel_view_models((runtime,))

    assert len(result) == 1
    assert result[0].title == "ChatGPT"
    assert result[0].bounds.width == 300
    assert result[0].kind == "browser"
