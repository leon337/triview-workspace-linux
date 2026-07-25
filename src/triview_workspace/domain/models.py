"""Domain contracts for workspaces, layouts and panels."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class PanelKind(str, Enum):
    """Panel categories supported by adapters."""

    BROWSER = "browser"
    APPLICATION = "application"
    TERMINAL = "terminal"
    PDF = "pdf"
    CUSTOM = "custom"


@dataclass(frozen=True, slots=True)
class NormalizedRect:
    """Rectangle represented as percentages in the inclusive range 0..1."""

    x: float
    y: float
    width: float
    height: float
    aspect_ratio: float | None = None

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(value < 0 or value > 1 for value in values):
            raise ValueError("Normalized rectangle values must be between 0 and 1.")
        if self.width == 0 or self.height == 0:
            raise ValueError("Normalized rectangle width and height must be greater than zero.")
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("Normalized rectangle must fit inside the viewport.")
        if self.aspect_ratio is not None and self.aspect_ratio <= 0:
            raise ValueError("Aspect ratio must be greater than zero.")


@dataclass(frozen=True, slots=True)
class PixelRect:
    """Calculated panel bounds in physical pixels."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class PanelSpec:
    """Persistent description of one panel."""

    id: str
    title: str
    kind: PanelKind
    target: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LayoutSpec:
    """Persistent proportional layout."""

    id: str
    name: str
    slots: tuple[NormalizedRect, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceSpec:
    """Persistent workspace configuration."""

    id: str
    name: str
    layout_id: str
    panels: tuple[PanelSpec, ...]


@dataclass(frozen=True, slots=True)
class RuntimePanel:
    """Panel prepared for a concrete adapter and calculated viewport."""

    panel: PanelSpec
    bounds: PixelRect
    adapter_name: str
    launch_request: Mapping[str, Any]
