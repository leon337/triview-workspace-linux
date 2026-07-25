#!/usr/bin/env bash
set -Eeuo pipefail

VERSION="0.1.2"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
PACKAGE_DIR=""
LEGACY_OVERRIDE=""
DRY_RUN=0
ASSUME_YES=0

while (($#)); do
  case "$1" in
    --source) SOURCE_DIR="${2:?Diretório ausente}"; shift 2 ;;
    --package-dir) PACKAGE_DIR="${2:?Diretório ausente}"; shift 2 ;;
    --legacy-dir) LEGACY_OVERRIDE="${2:?Diretório ausente}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --help|-h)
      printf 'Uso: migrate-legacy.sh [--source DIR] [--package-dir DIR] [--legacy-dir DIR] [--dry-run] [--yes]\n'
      exit 0
      ;;
    *) printf 'Opção desconhecida: %s\n' "$1" >&2; exit 2 ;;
  esac
done

HOME_DIR="${HOME:?HOME não definido}"
LEGACY_APP="$HOME_DIR/.local/share/triview-workspace-linux"
LEGACY_CONFIG="$HOME_DIR/.config/triview-workspace"
APP_ROOT="$HOME_DIR/.local/share/triview-workspace"
RELEASE_DIR="$APP_ROOT/releases/$VERSION"
CURRENT_LINK="$APP_ROOT/current"
BACKUP_ROOT="$HOME_DIR/.local/share/triview-workspace-backups"
BIN_DIR="$HOME_DIR/.local/bin"
APPLICATIONS_DIR="$HOME_DIR/.local/share/applications"
LOG_DIR="$HOME_DIR/.local/state/triview-workspace"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"
LOG_FILE="$LOG_DIR/migration-$TIMESTAMP.log"
PREVIOUS_CURRENT=""
CREATED_RELEASE=0

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

log() { printf '[TriView Migrador] %s\n' "$*"; }
fail() { log "ERRO: $*"; exit 1; }
run() {
  if ((DRY_RUN)); then
    printf '[DRY-RUN]'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

is_legacy() {
  local dir="$1" marker
  [[ -d "$dir" ]] || return 1
  for marker in app.py launcher.sh update.sh VERSION; do
    [[ -e "$dir/$marker" ]] || return 1
  done
}

detect_legacy() {
  if [[ -n "$LEGACY_OVERRIDE" ]]; then
    is_legacy "$LEGACY_OVERRIDE" || fail "Diretório legado inválido: $LEGACY_OVERRIDE"
    printf '%s\n' "$LEGACY_OVERRIDE"
    return
  fi
  if is_legacy "$LEGACY_APP"; then
    printf '%s\n' "$LEGACY_APP"
    return
  fi
  local candidate="${PACKAGE_DIR:-$SOURCE_DIR}"
  candidate="$(cd -- "$candidate" 2>/dev/null && pwd || printf '%s' "$candidate")"
  for _ in 1 2 3 4 5; do
    if is_legacy "$candidate"; then printf '%s\n' "$candidate"; return; fi
    [[ "$candidate" == "/" ]] && break
    candidate="$(dirname -- "$candidate")"
  done
  printf '\n'
}

rollback() {
  local code=$?
  ((code == 0 || DRY_RUN)) && return
  log "Falha detectada; restaurando o ponteiro anterior."
  ((CREATED_RELEASE)) && rm -rf -- "$RELEASE_DIR" || true
  rm -f -- "$CURRENT_LINK" || true
  if [[ -n "$PREVIOUS_CURRENT" && -e "$PREVIOUS_CURRENT" ]]; then
    ln -s "$PREVIOUS_CURRENT" "$CURRENT_LINK" || true
  fi
  log "A instalação antiga permaneceu intacta. Log: $LOG_FILE"
}
trap rollback EXIT

[[ "$(uname -s)" == "Linux" ]] || fail "Este migrador suporta somente Linux."
command -v python3 >/dev/null 2>&1 || fail "python3 não encontrado."
[[ -f "$SOURCE_DIR/pyproject.toml" ]] || fail "pyproject.toml ausente em $SOURCE_DIR"
[[ -d "$SOURCE_DIR/src/triview_workspace" ]] || fail "Código da aplicação ausente."

LEGACY_DETECTED="$(detect_legacy)"
log "Nova versão: $VERSION"
log "Origem: $SOURCE_DIR"
log "Destino: $RELEASE_DIR"
log "Instalação antiga: ${LEGACY_DETECTED:-não localizada}"
log "Backup: $BACKUP_DIR"

if ((!ASSUME_YES && !DRY_RUN)); then
  printf '\nContinuar? [s/N] '
  read -r answer
  [[ "$answer" =~ ^[sS]$ ]] || fail "Migração cancelada."
fi

if [[ -L "$CURRENT_LINK" ]]; then PREVIOUS_CURRENT="$(readlink -f "$CURRENT_LINK" || true)"; fi
run mkdir -p "$BACKUP_DIR" "$APP_ROOT/releases" "$APP_ROOT/data" "$BIN_DIR" "$APPLICATIONS_DIR"

if [[ -n "$LEGACY_DETECTED" ]]; then
  run mkdir -p "$BACKUP_DIR/legacy-app"
  run cp -a "$LEGACY_DETECTED/." "$BACKUP_DIR/legacy-app/"
fi
if [[ -d "$LEGACY_CONFIG" ]]; then
  run mkdir -p "$BACKUP_DIR/legacy-config" "$APP_ROOT/data/legacy-config"
  run cp -a "$LEGACY_CONFIG/." "$BACKUP_DIR/legacy-config/"
  run cp -a "$LEGACY_CONFIG/." "$APP_ROOT/data/legacy-config/"
fi

run rm -rf -- "$RELEASE_DIR"
run mkdir -p "$RELEASE_DIR"
run cp -a "$SOURCE_DIR/." "$RELEASE_DIR/"
CREATED_RELEASE=1

if ((!DRY_RUN)); then
  python3 -m compileall -q "$RELEASE_DIR/src"
  PYTHONPATH="$RELEASE_DIR/src" python3 -m triview_workspace.cli \
    --diagnostic --workspace "$RELEASE_DIR/config/workspaces/three-mobile.json" >/dev/null
  temp_link="$APP_ROOT/.current-$TIMESTAMP"
  ln -s "$RELEASE_DIR" "$temp_link"
  mv -Tf "$temp_link" "$CURRENT_LINK"
fi

write_launchers() {
  cat > "$BIN_DIR/triview-workspace" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
CURRENT="$APP_ROOT/current"
export PYTHONPATH="\$CURRENT/src\${PYTHONPATH:+:\$PYTHONPATH}"
cd "\$CURRENT"
exec python3 -m triview_workspace.cli "\$@"
EOF
  cat > "$BIN_DIR/triview-workspace-update" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$APP_ROOT/current/scripts/update.sh" "\$@"
EOF
  cat > "$BIN_DIR/triview-workspace-restore" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$APP_ROOT/current/scripts/restore-latest.sh" "\$@"
EOF
  chmod +x "$BIN_DIR"/triview-workspace*

  cat > "$APPLICATIONS_DIR/triview-workspace.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TriView Workspace
Comment=Plataforma modular de áreas de trabalho
Exec=$BIN_DIR/triview-workspace
Icon=preferences-desktop-display
Terminal=false
Categories=Utility;Development;
StartupNotify=true
EOF
  cat > "$APPLICATIONS_DIR/triview-workspace-update.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Atualizar TriView Workspace
Exec=$BIN_DIR/triview-workspace-update
Icon=system-software-update
Terminal=true
Categories=Utility;Development;
EOF
  cat > "$APPLICATIONS_DIR/triview-workspace-restore.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Restaurar TriView Workspace
Exec=$BIN_DIR/triview-workspace-restore
Icon=document-revert
Terminal=true
Categories=Utility;Development;
EOF
  chmod +x "$APPLICATIONS_DIR"/triview-workspace*.desktop
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
}

if ((DRY_RUN)); then
  log "[DRY-RUN] criar comandos e atalhos gráficos."
else
  write_launchers
  printf '%s\n' "$VERSION" > "$APP_ROOT/VERSION"
  cat > "$APP_ROOT/migration-state.json" <<EOF
{"version":"$VERSION","migrated_at":"$TIMESTAMP","backup":"$BACKUP_DIR"}
EOF
fi

trap - EXIT
log "Migração concluída. A instalação antiga não foi apagada."
log "Versão ativa: $VERSION"
log "Backup: $BACKUP_DIR"
