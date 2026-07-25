"""Display-oriented view models that do not depend on a graphical server."""

from __future__ import annotations

from dataclasses import dataclass

from triview_workspace.domain import PixelRect, RuntimePanel


@dataclass(frozen=True, slots=True)
class PanelViewModel:
    id: str
    title: str
    kind: str
    target: str
    status: str
    bounds: PixelRect
    adapter_name: str = "placeholder"


def panel_status(kind: str, adapter_name: str = "placeholder") -> str:
    messages = {
        "browser": "Navegador pronto para abertura dentro deste painel",
        "application": "Aplicação Linux pronta para abertura dentro ou fora deste painel",
        "terminal": "Terminal Linux pronto para abertura dentro ou fora deste painel",
        "pdf": "PDF pronto para abertura dentro ou fora deste painel",
        "plugin": "Plugin declarativo pronto para validação e abertura",
    }
    if adapter_name in messages:
        return messages[adapter_name]
    labels = {
        "browser": "Navegador ainda não possui backend funcional neste painel",
        "application": "Aplicação ainda não possui backend funcional neste painel",
        "terminal": "Terminal ainda não possui backend funcional neste painel",
        "pdf": "Visualizador PDF ainda não possui backend funcional neste painel",
        "custom": "Plugin ainda não possui manifesto válido e ativo",
    }
    return labels.get(kind, "Painel preparado para adaptador futuro")


def build_panel_view_models(
    runtime_panels: tuple[RuntimePanel, ...],
) -> tuple[PanelViewModel, ...]:
    return tuple(
        PanelViewModel(
            id=runtime.panel.id,
            title=runtime.panel.title,
            kind=runtime.panel.kind.value,
            target=runtime.panel.target,
            status=panel_status(runtime.panel.kind.value, runtime.adapter_name),
            bounds=runtime.bounds,
            adapter_name=runtime.adapter_name,
        )
        for runtime in runtime_panels
    )
