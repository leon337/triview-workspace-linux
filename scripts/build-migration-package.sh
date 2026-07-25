#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(python3 - <<PY
from pathlib import Path
import re
text=Path('$ROOT/pyproject.toml').read_text(encoding='utf-8')
print(re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE).group(1))
PY
)"
OUT="${1:-$ROOT/dist}"
NAME="TriView-Workspace-Migrador-$VERSION"
STAGE="$OUT/$NAME"
rm -rf "$STAGE"
mkdir -p "$STAGE/app"
cp -a "$ROOT/packaging/MIGRAR.desktop" "$ROOT/packaging/RESTAURAR.desktop" \
  "$ROOT/packaging/migrar.sh" "$ROOT/packaging/restaurar.sh" \
  "$ROOT/packaging/README-MIGRACAO.txt" "$STAGE/"
cp -a "$ROOT/src" "$ROOT/config" "$ROOT/docs" "$ROOT/scripts" \
  "$ROOT/tests" "$ROOT/pyproject.toml" "$ROOT/README.md" "$ROOT/CHANGELOG.md" "$STAGE/app/"
find "$STAGE" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$STAGE" -type f -name '*.pyc' -delete
chmod +x "$STAGE"/*.sh "$STAGE"/*.desktop "$STAGE/app/scripts"/*.sh
mkdir -p "$OUT"
(
  cd "$OUT"
  rm -f "$NAME.zip" "$NAME.tar.gz"
  zip -qr "$NAME.zip" "$NAME"
  tar -czf "$NAME.tar.gz" "$NAME"
)
printf '%s\n' "$OUT/$NAME.zip" "$OUT/$NAME.tar.gz"
