#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="TriView Workspace"
VERSION="0.1.1"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
HOME_DIR="${HOME:?HOME não definido}"
LEGACY_APP_DIR="$HOME_DIR/.local/share/triview-workspace-linux"
LEGACY_CONFIG_DIR="$HOME_DIR/.config/triview-workspace"
APP_ROOT="$HOME_DIR/.local/share/triview-workspace"
RELEASE_DIR="$APP_ROOT/releases/$VERSION"
CURRENT_LINK="$APP_ROOT/current"
DATA_DIR="$APP_ROOT/data"
BACKUP_ROOT="$HOME_DIR/.local/share/triview-workspace-backups"
BIN_DIR="$HOME_DIR/.local/bin"
APPLICATIONS_DIR="$HOME_DIR/.local/share/applications"
LOG_DIR="$HOME_DIR/.local/state/triview-workspace"
LOG_FILE="$LOG_DIR/migration-$(date +%Y%m%d-%H%M%S).log"
DRY_RUN=0
ASSUME_YES=0
PACKAGE_DIR=""
EXPLICIT_LEGACY_DIR=""
PREVIOUS_CURRENT=""
CREATED_RELEASE=0

usage() {
  cat <<'EOF'
Uso: migrate-legacy.sh [opções]

Opções:
  --source DIR       Diretório da nova aplicação a instalar.
  --package-dir DIR  Diretório do pacote extraído, usado para detectar a versão antiga ao redor.
  --legacy-dir DIR   Força o diretório da instalação antiga.
  --dry-run          Mostra todas as ações sem alterar arquivos.
  --yes              Não solicita confirmação.
  --help             Exibe esta ajuda.
EOF
}

while (($#)); do
  case "$1" in
    --source) SOURCE_DIR="${2:?Diretório ausente}"; shift 2 ;;
    --package-dir) PACKAGE_DIR="${2:?Diretório ausente}"; shift 2 ;;
    --legacy-dir) EXPLICIT_LEGACY_DIR="${2:?Diretório ausente}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) printf 'Opção desconhecida: %s\n' "$1" >&2; usage; exit 2 ;;
  esac
done

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

legacy_markers_present() {
  local dir="$1" marker
  [[ -d "$dir" ]] || return 1
  for marker in app.py launcher.sh update.sh VERSION; do
    [[ -e "$dir/$marker" ]] || return 1
  done
}

detect_legacy_dir() {
  if [[ -n "$EXPLICIT_LEGACY_DIR" ]]; then
    legacy_markers_present "$EXPLICIT_LEGACY_DIR" || fail "O diretório informado não corresponde à instalação antiga: $EXPLICIT_LEGACY_DIR"
    printf '%s\n' "$EXPLICIT_LEGACY_DIR"
    return
  fi
  if legacy_markers_present "$LEGACY_APP_DIR"; then
    printf '%s\n' "$LEGACY_APP_DIR"
    return
  fi
  local candidate
  candidate="${PACKAGE_DIR:-$SOURCE_DIR}"
  candidate="$(cd -- "$candidate" 2>/dev/null && pwd || printf '%s' "$candidate")"
  for _ in 1 2 3 4 5; do
    if legacy_markers_present "$candidate"; then
      printf '%s\n' "$candidate"
      return
    fi
    [[ "$candidate" == "/" ]] && break
    candidate="$(dirname -- "$candidate")"
  done
  printf '\n'
}

rollback() {
  local code=$?
  ((code == 0 || DRY_RUN)) && return
  log "Falha detectada. Restaurando o estado anterior da nova instalação..."
  if ((CREATED_RELEASE)) && [[ -d "$RELEASE_DIR" ]]; then
    rm -rf -- "$RELEASE_DIR" || true
  fi
  rm -f -- "$CURRENT_LINK" || true
  if [[ -n "$PREVIOUS_CURRENT" && -e "$PREVIOUS_CURRENT" ]]; then
    ln -s "$PREVIOUS_CURRENT" "$CURRENT_LINK" || true
  fi
  log "A instalação antiga permaneceu intacta. Log: $LOG_FILE"
}
trap rollback EXIT

[[ "$(uname -s)" == "Linux" ]] || fail "Este migrador suporta somente Linux."
command -v python3 >/dev/null 2>&1 || fail "python3 não encontrado."
command -v cp >/dev/null 2>&1 || fail "cp não encontrado."
command -v tar >/dev/null 2>&1 || fail "tar não encontrado."
[[ -f "$SOURCE_DIR/pyproject.toml" && -d "$SOURCE_DIR/src/triview_workspace" ]] || fail "O pacote não contém a nova aplicação em $SOURCE_DIR."

LEGACY_DETECTED="$(detect_legacy_dir)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

log "Plano de migração"
log "Origem nova: $SOURCE_DIR"
log "Instalação nova: $RELEASE_DIR"
log "Configuração preservada: $LEGACY_CONFIG_DIR"
if [[ -n "$LEGACY_DETECTED" ]]; then
  log "Instalação antiga detectada: $LEGACY_DETECTED"
else
  log "Instalação antiga não localizada; será feita uma instalação limpa e segura."
fi
log "Backup: $BACKUP_DIR"

if ((DRY_RUN)); then
  log "Modo de simulação: nenhuma alteração será realizada."
fi

if ((!ASSUME_YES && !DRY_RUN)); then
  printf '\nContinuar com a migração? [s/N] '
  read -r answer
  [[ "$answer" =~ ^[sS]$ ]] || fail "Migração cancelada pelo usuário."
fi

if [[ -L "$CURRENT_LINK" ]]; then
  PREVIOUS_CURRENT="$(readlink -f "$CURRENT_LINK" || true)"
fi

run mkdir -p "$BACKUP_DIR" "$APP_ROOT/releases" "$DATA_DIR" "$BIN_DIR" "$APPLICATIONS_DIR"

if [[ -n "$LEGACY_DETECTED" ]]; then
  log "Criando backup integral da aplicação antiga..."
  run mkdir -p "$BACKUP_DIR/legacy-app"
  run cp -a "$LEGACY_DETECTED/." "$BACKUP_DIR/legacy-app/"
fi

if [[ -d "$LEGACY_CONFIG_DIR" ]]; then
  log "Criando backup das URLs e configurações..."
  run mkdir -p "$BACKUP_DIR/legacy-config"
  run cp -a "$LEGACY_CONFIG_DIR/." "$BACKUP_DIR/legacy-config/"
  run mkdir -p "$DATA_DIR/legacy-config"
  run cp -a "$LEGACY_CONFIG_DIR/." "$DATA_DIR/legacy-config/"
fi

if [[ -d "$APP_ROOT" && -n "$(find "$APP_ROOT" -mindepth 1 -maxdepth 1 ! -name releases ! -name data -print -quit 2>/dev/null)" ]]; then
  log "Registrando arquivos existentes da nova instalação no backup..."
  run mkdir -p "$BACKUP_DIR/previous-new-install"
  if ((!DRY_RUN)); then
    find "$APP_ROOT" -mindepth 1 -maxdepth 1 ! -name releases ! -name data -exec cp -a {} "$BACKUP_DIR/previous-new-install/" \;
  fi
fi

log "Instalando a versão $VERSION em diretório versionado..."
run rm -rf -- "$RELEASE_DIR"
run mkdir -p "$RELEASE_DIR"
run cp -a "$SOURCE_DIR/." "$RELEASE_DIR/"
CREATED_RELEASE=1

if ((!DRY_RUN)); then
  python3 -m compileall -q "$RELEASE_DIR/src"
fi

log "Atualizando ponteiro atômico da versão atual..."
if ((DRY_RUN)); then
  log "[DRY-RUN] ln -sfn $RELEASE_DIR $CURRENT_LINK"
else
  temp_link="$APP_ROOT/.current-$TIMESTAMP"
  ln -s "$RELEASE_DIR" "$temp_link"
  mv -Tf "$temp_link" "$CURRENT_LINK"
fi

cat_launcher() {
  cat <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
APP_ROOT="$APP_ROOT"
CURRENT="\$APP_ROOT/current"
export PYTHONPATH="\$CURRENT/src\${PYTHONPATH:+:\$PYTHONPATH}"
cd "\$CURRENT"
exec python3 -m triview_workspace.cli "\$@"
EOF
}

cat_updater() {
  cat <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$APP_ROOT/current/scripts/update.sh" "\$@"
EOF
}

cat_restorer() {
  cat <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$APP_ROOT/current/scripts/restore-latest.sh" "\$@"
EOF
}

write_file() {
  local target="$1" mode="$2" content_function="$3"
  if ((DRY_RUN)); then
    log "[DRY-RUN] criar $target"
    return
  fi
  "$content_function" > "$target"
  chmod "$mode" "$target"
}

log "Criando comandos do usuário..."
write_file "$BIN_DIR/triview-workspace" 0755 cat_launcher
write_file "$BIN_DIR/triview-workspace-update" 0755 cat_updater
write_file "$BIN_DIR/triview-workspace-restore" 0755 cat_restorer

create_desktop_entries() {
  cat > "$APPLICATIONS_DIR/triview-workspace.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TriView Workspace
Comment=Plataforma modular de áreas de trabalho
Exec=$BIN_DIR/triview-workspace
Icon=utilities-terminal
Terminal=true
Categories=Utility;Development;
StartupNotify=true
EOF
  cat > "$APPLICATIONS_DIR/triview-workspace-update.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Atualizar TriView Workspace
Comment=Atualiza com backup e preservação de dados
Exec=$BIN_DIR/triview-workspace-update
Icon=system-software-update
Terminal=true
Categories=Utility;Development;
EOF
  cat > "$APPLICATIONS_DIR/triview-workspace-restore.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Restaurar TriView Workspace
Comment=Restaura o backup mais recente da instalação antiga
Exec=$BIN_DIR/triview-workspace-restore
Icon=document-revert
Terminal=true
Categories=Utility;Development;
EOF
  chmod +x "$APPLICATIONS_DIR"/triview-workspace*.desktop
}

log "Criando atalhos no menu..."
if ((DRY_RUN)); then
  log "[DRY-RUN] criar atalhos em $APPLICATIONS_DIR"
else
  create_desktop_entries
  update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
fi

log "Validando a nova instalação..."
if ((!DRY_RUN)); then
  "$BIN_DIR/triview-workspace" --workspace "$CURRENT_LINK/config/workspaces/three-mobile.json" >/dev/null
  printf '%s\n' "$VERSION" > "$APP_ROOT/VERSION"
  cat > "$APP_ROOT/migration-state.json" <<EOF
{
  "version": "$VERSION",
  "migrated_at": "$TIMESTAMP",
  "legacy_app": "$LEGACY_DETECTED",
  "legacy_config": "$LEGACY_CONFIG_DIR",
  "backup": "$BACKUP_DIR"
}
EOF
fi

trap - EXIT
log "Migração concluída com sucesso."
log "Backup criado em: $BACKUP_DIR"
log "A instalação antiga não foi apagada."
log "Versão ativa: $VERSION"
