"""Display-oriented view models that do not depend on a graphical server."""

from __future__ import annotations

from dataclasses import dataclass

from triview_workspace.domain import PixelRect, RuntimePanel


@dataclass(frozen=True, slots=True)
class PanelViewModel:
    """Data required by the desktop shell to render one panel."""

    id: str
    title: str
    kind: str
    target: str
    status: str
    bounds: PixelRect
    adapter_name: str = "placeholder"


def panel_status(kind: str, adapter_name: str = "placeholder") -> str:
    """Return the integration status shown in the shell."""

    if adapter_name == "browser":
        return "Navegador pronto para abertura dentro deste painel"

    labels = {
        "browser": "Navegador ainda não possui backend funcional neste painel",
        "application": "Aplicação externa será incorporada em uma etapa posterior",
        "terminal": "Terminal será incorporado em uma etapa posterior",
        "pdf": "Visualizador de PDF será incorporado em uma etapa posterior",
    }
    return labels.get(kind, "Painel preparado para adaptador futuro")


def build_panel_view_models(runtime_panels: tuple[RuntimePanel, ...]) -> tuple[PanelViewModel, ...]:
    """Convert runtime panels into immutable GUI-ready values."""

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
