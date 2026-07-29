"""Panel-scoped still-image capture with X11 backends and audit metadata."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from triview_workspace.engines.panel_runtime import safe_panel_token


class CaptureEngineError(RuntimeError):
    """Base error raised by panel image capture operations."""


@dataclass(frozen=True, slots=True)
class CaptureAvailability:
    available: bool
    reason: str
    backend: str | None = None
    command: str | None = None


@dataclass(frozen=True, slots=True)
class CaptureRequest:
    workspace_id: str
    panel_id: str
    panel_title: str
    window_id: int
    output_path: Path


@dataclass(frozen=True, slots=True)
class CaptureResult:
    workspace_id: str
    panel_id: str
    panel_title: str
    path: str
    created_at: str
    backend: str
    window_id: int


class CaptureBackend(Protocol):
    def availability(self) -> CaptureAvailability: ...

    def capture(self, request: CaptureRequest) -> str: ...


class X11CaptureBackend:
    """Capture one X11 window using maim or ImageMagick import."""

    def availability(self) -> CaptureAvailability:
        if not os.environ.get("DISPLAY"):
            return CaptureAvailability(
                False,
                "A captura exige uma sessão gráfica X11 com DISPLAY disponível.",
            )
        maim = shutil.which("maim")
        if maim:
            return CaptureAvailability(True, "Backend maim disponível.", "maim", maim)
        imagemagick_import = shutil.which("import")
        if imagemagick_import:
            return CaptureAvailability(
                True,
                "Backend ImageMagick import disponível.",
                "imagemagick-import",
                imagemagick_import,
            )
        return CaptureAvailability(
            False,
            "Instale maim ou ImageMagick para capturar painéis no X11.",
        )

    def capture(self, request: CaptureRequest) -> str:
        report = self.availability()
        if not report.available or not report.command or not report.backend:
            raise CaptureEngineError(report.reason)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = request.output_path.with_name(
            f".{request.output_path.stem}.partial{request.output_path.suffix}"
        )
        temporary.unlink(missing_ok=True)
        if report.backend == "maim":
            command = [report.command, "-i", str(request.window_id), str(temporary)]
        else:
            command = [
                report.command,
                "-silent",
                "-window",
                str(request.window_id),
                str(temporary),
            ]
        try:
            result = subprocess.run(  # noqa: S603
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            temporary.unlink(missing_ok=True)
            raise CaptureEngineError(f"Falha ao executar a captura: {exc}.") from exc
        if result.returncode != 0 or not temporary.is_file():
            temporary.unlink(missing_ok=True)
            detail = result.stderr.strip() or result.stdout.strip() or "arquivo não gerado"
            raise CaptureEngineError(f"A captura do painel falhou: {detail}.")
        temporary.replace(request.output_path)
        return report.backend


class CaptureEngine:
    """Organize panel captures and append an auditable JSONL history."""

    def __init__(
        self,
        backend: CaptureBackend | None = None,
        root: str | Path | None = None,
    ) -> None:
        self.backend = backend or X11CaptureBackend()
        configured = os.environ.get("TRIVIEW_CAPTURE_DIR")
        self.root = Path(root or configured or (Path.home() / "Pictures" / "TriView Workspace" / "Captures"))
        self._history_lock = threading.Lock()

    def availability(self) -> CaptureAvailability:
        return self.backend.availability()

    def capture(
        self,
        workspace_id: str,
        panel_id: str,
        panel_title: str,
        window_id: int,
        now: datetime | None = None,
    ) -> CaptureResult:
        if int(window_id) <= 0:
            raise CaptureEngineError("O identificador da janela do painel é inválido.")
        timestamp = (now or datetime.now().astimezone()).astimezone()
        workspace_token = safe_panel_token(workspace_id)
        panel_token = safe_panel_token(panel_id)
        day = timestamp.strftime("%Y-%m-%d")
        filename = timestamp.strftime("%H%M%S-%f") + ".png"
        output = self.root / workspace_token / panel_token / day / filename
        request = CaptureRequest(
            workspace_id=workspace_id,
            panel_id=panel_id,
            panel_title=panel_title,
            window_id=int(window_id),
            output_path=output,
        )
        backend_name = self.backend.capture(request)
        result = CaptureResult(
            workspace_id=workspace_id,
            panel_id=panel_id,
            panel_title=panel_title,
            path=str(output),
            created_at=timestamp.isoformat(),
            backend=backend_name,
            window_id=int(window_id),
        )
        self._append_history(result)
        return result

    @property
    def history_path(self) -> Path:
        return self.root / "capture-history.jsonl"

    def _append_history(self, result: CaptureResult) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(asdict(result), ensure_ascii=False, sort_keys=True)
        with self._history_lock:
            with self.history_path.open("a", encoding="utf-8") as handle:
                handle.write(serialized + "\n")
                handle.flush()
                os.fsync(handle.fileno())
