"""PDF panel adapter and engine built on the shared Panel Runtime."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeLaunchRequest,
    PanelRuntimeSession,
    X11PanelRuntimeBackend,
    safe_panel_token,
)

LOGGER = logging.getLogger(__name__)
_VIEWER_CANDIDATES = ("xreader", "evince", "atril", "okular", "zathura", "mupdf")


class PdfEngineError(RuntimeError):
    """Base error raised by PDF panel operations."""


@dataclass(frozen=True, slots=True)
class PdfAvailability:
    available: bool
    can_embed: bool
    reason: str
    viewer: str | None = None
    document: str | None = None


def normalize_pdf_path(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise ValueError("O caminho do PDF não pode ficar vazio.")
    path = Path(raw).expanduser()
    if path.suffix.lower() != ".pdf":
        raise ValueError("O arquivo precisa usar a extensão .pdf.")
    if not path.is_file():
        raise ValueError(f"O arquivo PDF não foi encontrado: {path}.")
    return str(path.resolve())


class PdfPanelAdapter:
    name = "pdf"

    def supports(self, kind: PanelKind) -> bool:
        return kind is PanelKind.PDF

    def build_launch_request(self, panel: PanelSpec) -> dict[str, object]:
        return {
            "mode": "pdf",
            "panel_id": panel.id,
            "document": normalize_pdf_path(panel.target),
        }


class X11PdfBackend:
    def __init__(self, runtime: X11PanelRuntimeBackend | None = None) -> None:
        self._runtime = runtime or X11PanelRuntimeBackend()

    @staticmethod
    def _viewer() -> str | None:
        return next(
            (
                resolved
                for candidate in _VIEWER_CANDIDATES
                if (resolved := shutil.which(candidate))
            ),
            None,
        )

    def availability(self, document: str) -> PdfAvailability:
        try:
            normalized = normalize_pdf_path(document)
        except ValueError as exc:
            return PdfAvailability(False, False, str(exc))
        viewer = self._viewer()
        if viewer is None:
            return PdfAvailability(
                False,
                False,
                "Nenhum visualizador PDF compatível foi encontrado.",
                document=normalized,
            )
        report = self._runtime.availability(self._command(viewer, normalized))
        return PdfAvailability(
            report.available,
            report.can_embed,
            report.reason,
            viewer=viewer,
            document=normalized,
        )

    def launch(
        self,
        panel_id: str,
        title: str,
        document: str,
        parent_window_id: int,
    ) -> PanelRuntimeSession:
        normalized = normalize_pdf_path(document)
        viewer = self._viewer()
        if viewer is None:
            raise PdfEngineError("Nenhum visualizador PDF compatível foi encontrado.")
        request = PanelRuntimeLaunchRequest(
            panel_id=panel_id,
            command=self._command(viewer, normalized),
            window_hints=(title, Path(viewer).name, safe_panel_token(panel_id), panel_id),
            allow_external_fallback=True,
        )
        return self._runtime.launch(request, parent_window_id)

    def resize(self, session: PanelRuntimeSession, width: int, height: int) -> None:
        self._runtime.resize(session, width, height)

    def close(self, session: PanelRuntimeSession) -> None:
        self._runtime.close(session)

    @staticmethod
    def _command(viewer: str, document: str) -> tuple[str, ...]:
        name = Path(viewer).name
        if name == "evince":
            return (viewer, "--new-window", document)
        if name == "okular":
            return (viewer, "--noraise", document)
        return (viewer, document)


class PdfEngine:
    def __init__(self, backend: X11PdfBackend | None = None) -> None:
        self._backend = backend or X11PdfBackend()
        self._sessions: dict[str, PanelRuntimeSession] = {}
        self._lock = RLock()

    def availability(self, target: str) -> PdfAvailability:
        return self._backend.availability(target)

    def has_session(self, panel_id: str) -> bool:
        with self._lock:
            return panel_id in self._sessions

    def open(
        self,
        panel_id: str,
        title: str,
        target: str,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> PanelRuntimeSession:
        with self._lock:
            previous = self._sessions.pop(panel_id, None)
        if previous is not None:
            self._backend.close(previous)
        session = self._backend.launch(panel_id, title, target, parent_window_id)
        try:
            if session.embedded:
                self._backend.resize(session, width, height)
        except Exception:
            try:
                self._backend.close(session)
            finally:
                raise
        with self._lock:
            self._sessions[panel_id] = session
        return session

    def resize(self, panel_id: str, width: int, height: int) -> None:
        with self._lock:
            session = self._sessions.get(panel_id)
        if session is not None:
            self._backend.resize(session, width, height)

    def close(self, panel_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(panel_id, None)
        if session is not None:
            self._backend.close(session)

    def close_all(self) -> None:
        with self._lock:
            sessions = tuple(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            try:
                self._backend.close(session)
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unable to close PDF panel %s", session.panel_id)
