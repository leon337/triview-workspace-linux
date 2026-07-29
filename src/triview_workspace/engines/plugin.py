"""Declarative, versioned and explicitly enabled command plugins."""

from __future__ import annotations

import json
import os
import re
import shlex
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from triview_workspace.domain import PanelKind, PanelSpec
from triview_workspace.engines.application import ApplicationEngine
from triview_workspace.engines.panel_runtime import (
    PanelRuntimeAvailability,
    PanelRuntimeSession,
    normalize_command,
    split_command,
)

PLUGIN_SCHEMA_VERSION = 1
PLUGIN_API_VERSION = "1"
_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9-]{1,62}$")


class PluginEngineError(RuntimeError):
    """Base error raised by plugin discovery or execution."""


@dataclass(frozen=True, slots=True)
class PluginManifest:
    schema_version: int
    api_version: str
    id: str
    name: str
    description: str
    command: tuple[str, ...]
    allow_arguments: bool
    directory: str


@dataclass(frozen=True, slots=True)
class PluginDiagnostic:
    plugin_id: str
    valid: bool
    enabled: bool
    message: str
    manifest_path: str


@dataclass(frozen=True, slots=True)
class PluginTarget:
    plugin_id: str
    arguments: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PluginOpenResult:
    embedded: bool
    external: bool


def parse_plugin_target(value: str) -> PluginTarget:
    raw = value.strip()
    if not raw.startswith("plugin:"):
        raise ValueError("O destino do plugin precisa começar com 'plugin:'.")
    payload = raw[len("plugin:") :].strip()
    if not payload:
        raise ValueError("Informe o identificador do plugin.")
    parts = split_command(payload)
    plugin_id = parts[0]
    if not _PLUGIN_ID.fullmatch(plugin_id):
        raise ValueError("O identificador do plugin é inválido.")
    return PluginTarget(plugin_id, parts[1:])


class PluginPanelAdapter:
    """Prepare custom panels without loading executable code into the core."""

    name = "plugin"

    def supports(self, kind: PanelKind) -> bool:
        return kind is PanelKind.CUSTOM

    def build_launch_request(self, panel: PanelSpec) -> dict[str, object]:
        try:
            target = parse_plugin_target(panel.target)
            return {
                "mode": "plugin",
                "plugin_id": target.plugin_id,
                "arguments": target.arguments,
            }
        except ValueError:
            # Runtime diagnostics remain available even for a malformed saved target.
            return {"mode": "plugin", "target": panel.target}


class PluginEngine:
    """Discover declarative manifests and execute only explicitly enabled plugins."""

    def __init__(
        self,
        application_engine: ApplicationEngine,
        root: str | Path | None = None,
        state_path: str | Path | None = None,
    ) -> None:
        data_root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        self.root = Path(root) if root is not None else data_root / "triview-workspace" / "plugins"
        self.state_path = (
            Path(state_path)
            if state_path is not None
            else data_root / "triview-workspace" / "enabled-plugins.json"
        )
        self.application_engine = application_engine
        self._manifests: dict[str, PluginManifest] = {}
        self._diagnostics: tuple[PluginDiagnostic, ...] = ()
        self._lock = threading.RLock()
        self.reload()

    def reload(self) -> tuple[PluginDiagnostic, ...]:
        enabled = self._load_enabled()
        manifests: dict[str, PluginManifest] = {}
        diagnostics: list[PluginDiagnostic] = []
        self.root.mkdir(parents=True, exist_ok=True)
        for directory in sorted(self.root.iterdir(), key=lambda item: item.name):
            if not directory.is_dir() or directory.is_symlink():
                continue
            manifest_path = directory / "manifest.json"
            if not manifest_path.is_file() or manifest_path.is_symlink():
                continue
            try:
                manifest = self._read_manifest(directory, manifest_path)
            except Exception as exc:  # noqa: BLE001
                diagnostics.append(
                    PluginDiagnostic(
                        directory.name,
                        False,
                        False,
                        str(exc),
                        str(manifest_path),
                    )
                )
                continue
            manifests[manifest.id] = manifest
            diagnostics.append(
                PluginDiagnostic(
                    manifest.id,
                    True,
                    manifest.id in enabled,
                    "Plugin válido e ativo."
                    if manifest.id in enabled
                    else "Plugin válido, porém desativado.",
                    str(manifest_path),
                )
            )
        with self._lock:
            self._manifests = manifests
            self._diagnostics = tuple(diagnostics)
        return self._diagnostics

    def diagnostics(self) -> tuple[PluginDiagnostic, ...]:
        with self._lock:
            return self._diagnostics

    def enabled_ids(self) -> frozenset[str]:
        return frozenset(self._load_enabled())

    def enable(self, plugin_id: str) -> None:
        self.reload()
        with self._lock:
            if plugin_id not in self._manifests:
                raise PluginEngineError(f"O plugin '{plugin_id}' não é válido ou não existe.")
        enabled = self._load_enabled()
        enabled.add(plugin_id)
        self._save_enabled(enabled)
        self.reload()

    def disable(self, plugin_id: str) -> None:
        enabled = self._load_enabled()
        enabled.discard(plugin_id)
        self._save_enabled(enabled)
        self.application_engine.close_all()
        self.reload()

    def availability(self, target: str) -> PanelRuntimeAvailability:
        try:
            command = self.command_for(target)
        except (ValueError, PluginEngineError) as exc:
            return PanelRuntimeAvailability(False, False, str(exc))
        return self.application_engine.availability(shlex.join(command))

    def command_for(self, target: str) -> tuple[str, ...]:
        parsed = parse_plugin_target(target)
        enabled = self._load_enabled()
        with self._lock:
            manifest = self._manifests.get(parsed.plugin_id)
        if manifest is None:
            raise PluginEngineError(f"O plugin '{parsed.plugin_id}' não foi encontrado ou é inválido.")
        if parsed.plugin_id not in enabled:
            raise PluginEngineError(f"O plugin '{parsed.plugin_id}' está desativado.")
        if parsed.arguments and not manifest.allow_arguments:
            raise PluginEngineError(f"O plugin '{parsed.plugin_id}' não aceita argumentos adicionais.")
        return (*manifest.command, *parsed.arguments)

    def open(
        self,
        panel_id: str,
        target: str,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> PanelRuntimeSession:
        command = self.command_for(target)
        return self.application_engine.open(
            panel_id,
            shlex.join(command),
            parent_window_id,
            width,
            height,
        )

    def has_session(self, panel_id: str) -> bool:
        return self.application_engine.has_session(panel_id)

    def resize(self, panel_id: str, width: int, height: int) -> None:
        self.application_engine.resize(panel_id, width, height)

    def close(self, panel_id: str) -> None:
        self.application_engine.close(panel_id)

    def close_all(self) -> None:
        self.application_engine.close_all()

    def _read_manifest(self, directory: Path, path: Path) -> PluginManifest:
        if directory.resolve().parent != self.root.resolve():
            raise PluginEngineError("O diretório do plugin está fora da raiz permitida.")
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, Mapping):
            raise PluginEngineError("O manifesto precisa ser um objeto JSON.")
        schema_version = int(payload.get("schema_version", 0))
        if schema_version != PLUGIN_SCHEMA_VERSION:
            raise PluginEngineError("Versão de esquema do plugin incompatível.")
        api_version = str(payload.get("api_version", ""))
        if api_version != PLUGIN_API_VERSION:
            raise PluginEngineError("Versão da API do plugin incompatível.")
        plugin_id = str(payload.get("id", ""))
        if not _PLUGIN_ID.fullmatch(plugin_id) or plugin_id != directory.name:
            raise PluginEngineError("O ID do plugin é inválido ou difere do diretório.")
        name = str(payload.get("name", "")).strip()
        if not name:
            raise PluginEngineError("O plugin precisa de um nome.")
        command = payload.get("command")
        if not isinstance(command, str):
            raise PluginEngineError("O comando do plugin precisa ser uma string.")
        normalized = split_command(normalize_command(command))
        description = str(payload.get("description", "")).strip()
        allow_arguments = bool(payload.get("allow_arguments", False))
        return PluginManifest(
            schema_version,
            api_version,
            plugin_id,
            name,
            description,
            normalized,
            allow_arguments,
            str(directory.resolve()),
        )

    def _load_enabled(self) -> set[str]:
        if not self.state_path.is_file():
            return set()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(payload, Mapping) or payload.get("schema_version") != 1:
                return set()
            values = payload.get("enabled", [])
            if not isinstance(values, list):
                return set()
            return {str(item) for item in values if _PLUGIN_ID.fullmatch(str(item))}
        except (OSError, json.JSONDecodeError):
            return set()

    def _save_enabled(self, enabled: set[str]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "schema_version": 1,
            "enabled": sorted(enabled),
        }
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".enabled-plugins-",
            suffix=".json",
            dir=self.state_path.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(self.state_path)
        finally:
            temporary.unlink(missing_ok=True)


class PluginRuntimeController:
    adapter_name = "plugin"

    def __init__(self, engine: PluginEngine) -> None:
        self.engine = engine

    def availability(self, panel: PanelSpec) -> PanelRuntimeAvailability:
        return self.engine.availability(panel.target)

    def open(
        self,
        panel: PanelSpec,
        parent_window_id: int,
        width: int,
        height: int,
    ) -> PluginOpenResult:
        session = self.engine.open(panel.id, panel.target, parent_window_id, width, height)
        return PluginOpenResult(session.embedded, session.external)

    def has_session(self, panel_id: str) -> bool:
        return self.engine.has_session(panel_id)

    def resize(self, panel_id: str, width: int, height: int) -> None:
        self.engine.resize(panel_id, width, height)

    def close(self, panel_id: str) -> None:
        self.engine.close(panel_id)

    def close_all(self) -> None:
        self.engine.close_all()
