"""Central visual language for the TriView desktop interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from triview_workspace import __version__


@dataclass(frozen=True)
class Palette:
    """Named colors used by the desktop shell."""

    app: str = "#060b18"
    surface: str = "#0b1220"
    surface_raised: str = "#111b2e"
    surface_soft: str = "#17233a"
    surface_hover: str = "#21304a"
    border: str = "#2b3b57"
    border_focus: str = "#38bdf8"
    text: str = "#f8fafc"
    text_muted: str = "#9fb0c8"
    text_subtle: str = "#6f829f"
    accent: str = "#0ea5e9"
    accent_hover: str = "#38bdf8"
    accent_dark: str = "#075985"
    success: str = "#16a34a"
    warning: str = "#d97706"
    danger: str = "#dc2626"
    external: str = "#7c3aed"
    neutral: str = "#475569"


PALETTE: Final = Palette()
FONT_FAMILY: Final = "Sans"
MONO_FONT_FAMILY: Final = "Monospace"
APP_BADGE_TEXT: Final = f"TRIVIEW {__version__.replace('a', ' ALPHA ')}".upper()
WIDE_HEADER_MIN_WIDTH: Final = 1180

STATUS_COLORS: Final[dict[str, str]] = {
    "PLANEJADO": PALETTE.neutral,
    "DISPONÍVEL": "#0f766e",
    "INDISPONÍVEL": "#991b1b",
    "ABRINDO": PALETTE.warning,
    "ATIVO": PALETTE.success,
    "EXTERNO": PALETTE.external,
    "ERRO": PALETTE.danger,
    "GRAVANDO": "#b91c1c",
    "GRAVADO": "#15803d",
}


def status_color(status: str, fallback: str | None = None) -> str:
    """Return the semantic color for a runtime status."""

    return STATUS_COLORS.get(status.upper(), fallback or PALETTE.neutral)


def header_layout_mode(width: int) -> str:
    """Resolve the stable header arrangement for a viewport width."""

    return "wide" if width >= WIDE_HEADER_MIN_WIDTH else "compact"


def button_colors(variant: str = "secondary") -> dict[str, str]:
    """Return Tk button colors for one visual variant."""

    if variant == "primary":
        return {
            "background": PALETTE.accent_dark,
            "foreground": PALETTE.text,
            "activebackground": PALETTE.accent,
            "activeforeground": PALETTE.text,
        }
    if variant == "danger":
        return {
            "background": "#7f1d1d",
            "foreground": PALETTE.text,
            "activebackground": PALETTE.danger,
            "activeforeground": PALETTE.text,
        }
    if variant == "ghost":
        return {
            "background": PALETTE.surface,
            "foreground": PALETTE.text_muted,
            "activebackground": PALETTE.surface_hover,
            "activeforeground": PALETTE.text,
        }
    return {
        "background": PALETTE.surface_soft,
        "foreground": PALETTE.text,
        "activebackground": PALETTE.surface_hover,
        "activeforeground": PALETTE.text,
    }
