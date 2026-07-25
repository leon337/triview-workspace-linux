#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/triview-workspace"
PLUGIN_ROOT="$DATA_ROOT/plugins"
SOURCE="$ROOT/examples/plugins/text-editor"
DESTINATION="$PLUGIN_ROOT/text-editor"
STATE="$DATA_ROOT/enabled-plugins.json"

[[ -f "$SOURCE/manifest.json" ]] || {
  printf 'Manifesto de exemplo não encontrado em %s\n' "$SOURCE" >&2
  exit 1
}

mkdir -p "$PLUGIN_ROOT"
rm -rf "$DESTINATION"
cp -a "$SOURCE" "$DESTINATION"

python3 - "$STATE" <<'PY'
from __future__ import annotations
import json
import os
import sys
import tempfile
from pathlib import Path

path = Path(sys.argv[1])
enabled: set[str] = set()
if path.is_file():
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        enabled.update(str(item) for item in payload.get("enabled", []))
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
enabled.add("text-editor")
path.parent.mkdir(parents=True, exist_ok=True)
fd, name = tempfile.mkstemp(prefix=".plugins-", suffix=".json", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"schema_version": 1, "enabled": sorted(enabled)}, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    Path(name).replace(path)
finally:
    Path(name).unlink(missing_ok=True)
PY

printf 'Plugin text-editor instalado e ativado em %s\n' "$DESTINATION"
printf 'Use um painel custom com destino: plugin:text-editor\n'
