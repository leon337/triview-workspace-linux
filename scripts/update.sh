#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${TRIVIEW_REPO:-leon337/triview-workspace-linux}"
CHANNEL="${TRIVIEW_CHANNEL:-main}"
APP_DIR="${TRIVIEW_APP_DIR:-$HOME/.local/share/triview-workspace}"
BACKUP_ROOT="${TRIVIEW_BACKUP_ROOT:-$HOME/.local/share/triview-workspace-backups}"

log() {
  printf '[TriView Updater] %s\n' "$*"
}

fail() {
  printf '[TriView Updater] ERRO: %s\n' "$*" >&2
  exit 1
}

command -v curl >/dev/null 2>&1 || fail "curl não encontrado."
command -v tar >/dev/null 2>&1 || fail "tar não encontrado."

if [[ -d "$APP_DIR/.git" ]]; then
  command -v git >/dev/null 2>&1 || fail "git não encontrado."
  cd "$APP_DIR"
  [[ -z "$(git status --porcelain)" ]] || fail "Existem alterações locais. Faça backup antes."
  log "Atualizando instalação Git pela branch $CHANNEL..."
  git fetch origin "$CHANNEL"
  git checkout "$CHANNEL"
  git pull --ff-only origin "$CHANNEL"
  log "Atualização concluída."
  exit 0
fi

mkdir -p "$APP_DIR" "$BACKUP_ROOT"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="$BACKUP_ROOT/$timestamp"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

if [[ -n "$(find "$APP_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  log "Criando backup em $backup_dir..."
  mkdir -p "$backup_dir"
  cp -a "$APP_DIR/." "$backup_dir/"
fi

release_url="https://api.github.com/repos/$REPO/releases/latest"
archive_url="$(
  curl -fsSL "$release_url" |
    python3 -c 'import json,sys; print(json.load(sys.stdin)["tarball_url"])'
)" || fail "Não foi possível localizar a release mais recente."

log "Baixando release..."
curl -fL "$archive_url" -o "$tmp_dir/release.tar.gz"
mkdir -p "$tmp_dir/extracted"
tar -xzf "$tmp_dir/release.tar.gz" -C "$tmp_dir/extracted" --strip-components=1

data_tmp="$tmp_dir/user-data"
if [[ -d "$APP_DIR/data" ]]; then
  mv "$APP_DIR/data" "$data_tmp"
fi

find "$APP_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
cp -a "$tmp_dir/extracted/." "$APP_DIR/"

if [[ -d "$data_tmp" ]]; then
  mv "$data_tmp" "$APP_DIR/data"
fi

log "Atualização concluída. Backup: $backup_dir"
