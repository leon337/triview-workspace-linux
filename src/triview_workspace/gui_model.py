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


def panel_status(kind: str) -> str:
    """Return the temporary integration status shown in the shell."""

    labels = {
        "browser": "Navegador será incorporado na próxima etapa",
        "application": "Aplicação externa será incorporada na próxima etapa",
        "terminal": "Terminal será incorporado na próxima etapa",
        "pdf": "Visualizador de PDF será incorporado na próxima etapa",
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
            status=panel_status(runtime.panel.kind.value),
            bounds=runtime.bounds,
        )
        for runtime in runtime_panels
    )
