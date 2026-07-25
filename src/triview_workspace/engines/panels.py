"""Panel adapter registry."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from triview_workspace.domain import PanelKind, PanelSpec


class PanelAdapter(Protocol):
    """Contract implemented by browser, application and future panel adapters."""

    name: str

    def supports(self, kind: PanelKind) -> bool:
        """Return whether this adapter can prepare the panel kind."""

    def build_launch_request(self, panel: PanelSpec) -> Mapping[str, Any]:
        """Build an adapter-specific launch request without executing it."""


class PanelRegistry:
    """Resolves panel specifications to registered adapters."""

    def __init__(self) -> None:
        self._adapters: list[PanelAdapter] = []

    def register(self, adapter: PanelAdapter) -> None:
        if any(existing.name == adapter.name for existing in self._adapters):
            raise ValueError(f"Adapter already registered: {adapter.name}")
        self._adapters.append(adapter)

    def resolve(self, kind: PanelKind) -> PanelAdapter:
        for adapter in self._adapters:
            if adapter.supports(kind):
                return adapter
        raise LookupError(f"No panel adapter registered for kind: {kind.value}")


class PlaceholderPanelAdapter:
    """Foundation adapter used until real embedding adapters are delivered."""

    name = "placeholder"

    def supports(self, kind: PanelKind) -> bool:
        return kind in PanelKind

    def build_launch_request(self, panel: PanelSpec) -> Mapping[str, Any]:
        return {
            "mode": "placeholder",
            "panel_id": panel.id,
            "kind": panel.kind.value,
            "target": panel.target,
        }
