#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${TRIVIEW_REPO:-leon337/triview-workspace-linux}"
CHANNEL="${TRIVIEW_CHANNEL:-main}"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
BACKUP_ROOT="${TRIVIEW_BACKUP_ROOT:-$HOME/.local/share/triview-workspace-backups}"
CURRENT_LINK="$APP_ROOT/current"
DATA_DIR="$APP_ROOT/data"
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then DRY_RUN=1; shift; fi

log() { printf '[TriView Updater] %s\n' "$*"; }
fail() { log "ERRO: $*" >&2; exit 1; }
run() { if ((DRY_RUN)); then printf '[DRY-RUN]'; printf ' %q' "$@"; printf '\n'; else "$@"; fi; }

command -v curl >/dev/null 2>&1 || fail "curl não encontrado."
command -v tar >/dev/null 2>&1 || fail "tar não encontrado."
command -v python3 >/dev/null 2>&1 || fail "python3 não encontrado."

mkdir -p "$APP_ROOT/releases" "$BACKUP_ROOT" "$DATA_DIR"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="$BACKUP_ROOT/update-$timestamp"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

if [[ -L "$CURRENT_LINK" ]]; then
  current_target="$(readlink -f "$CURRENT_LINK")"
  run mkdir -p "$backup_dir"
  if ((DRY_RUN)); then
    log "[DRY-RUN] copiar versão atual para $backup_dir/current"
  else
    cp -a "$current_target" "$backup_dir/current"
  fi
fi

release_api="https://api.github.com/repos/$REPO/releases/latest"
archive_url=""
if archive_url="$(curl -fsSL "$release_api" 2>/dev/null | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("tarball_url", ""))' 2>/dev/null)" && [[ -n "$archive_url" ]]; then
  log "Usando a release estável mais recente."
else
  archive_url="https://github.com/$REPO/archive/refs/heads/$CHANNEL.tar.gz"
  log "Ainda não há release estável; usando a branch $CHANNEL."
fi

log "Baixando atualização..."
run curl -fL "$archive_url" -o "$tmp_dir/source.tar.gz"
run mkdir -p "$tmp_dir/extracted"
run tar -xzf "$tmp_dir/source.tar.gz" -C "$tmp_dir/extracted" --strip-components=1

if ((DRY_RUN)); then
  log "A validação e troca atômica seriam executadas agora."
  exit 0
fi

[[ -f "$tmp_dir/extracted/pyproject.toml" ]] || fail "Pacote baixado inválido."
[[ -d "$tmp_dir/extracted/src/triview_workspace" ]] || fail "Código da aplicação ausente."
python3 -m compileall -q "$tmp_dir/extracted/src"
version="$(python3 - <<PY
from pathlib import Path
import re
text = Path('$tmp_dir/extracted/pyproject.toml').read_text(encoding='utf-8')
match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
print(match.group(1) if match else '$timestamp')
PY
)"
release_dir="$APP_ROOT/releases/$version-$timestamp"
mkdir -p "$release_dir"
cp -a "$tmp_dir/extracted/." "$release_dir/"

export PYTHONPATH="$release_dir/src"
cd "$release_dir"
python3 -m triview_workspace.cli --workspace "$release_dir/config/workspaces/three-mobile.json" >/dev/null

temp_link="$APP_ROOT/.current-$timestamp"
ln -s "$release_dir" "$temp_link"
mv -Tf "$temp_link" "$CURRENT_LINK"
printf '%s\n' "$version" > "$APP_ROOT/VERSION"
log "Atualização concluída. Versão ativa: $version"
log "Backup: $backup_dir"
