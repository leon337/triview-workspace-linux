#!/usr/bin/env bash
set -Eeuo pipefail

EXECUTING_PATH="$(readlink -f "${BASH_SOURCE[0]}")"

# O núcleo legado pode substituir updater/update.sh durante a execução.
# O controlador continua a partir de uma cópia imutável e, depois da troca,
# instala os controladores pertencentes à release que ficou ativa.
if [[ "${TRIVIEW_UPDATER_CONTROLLER_SNAPSHOT:-0}" != "1" ]]; then
  snapshot="$(mktemp)"
  cp -a "$EXECUTING_PATH" "$snapshot"
  chmod +x "$snapshot"
  export TRIVIEW_UPDATER_CONTROLLER_SNAPSHOT=1
  export TRIVIEW_UPDATER_ORIGINAL_WRAPPER="$EXECUTING_PATH"
  exec bash "$snapshot" "$@"
fi

CONTROLLER_SOURCE="$EXECUTING_PATH"
ORIGINAL_WRAPPER="$(readlink -f "${TRIVIEW_UPDATER_ORIGINAL_WRAPPER:?caminho original ausente}")"
SCRIPT_DIR="$(dirname "$ORIGINAL_WRAPPER")"
CORE_SCRIPT="$SCRIPT_DIR/update-core.sh"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
CHANNEL_FILE="$APP_ROOT/UPDATE_CHANNEL"
UPDATER_ROOT="$APP_ROOT/updater"
STATE_BASE="${XDG_STATE_HOME:-$HOME/.local/state}"
STATE_ROOT="$STATE_BASE/triview-workspace"
LIFECYCLE_LOCK="$STATE_ROOT/lifecycle.lock"
BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="$HOME/.local/share/applications"

cleanup() {
  rm -f "$CONTROLLER_SOURCE" || true
  return 0
}
trap cleanup EXIT

for required_script in \
  update-core.sh \
  stable-launch.sh \
  stable-diagnose.sh \
  stable-rollback.sh; do
  [[ -f "$SCRIPT_DIR/$required_script" ]] || {
    printf '[TriView Updater] ERRO: controlador ausente: %s\n' \
      "$SCRIPT_DIR/$required_script" >&2
    exit 1
  }
done
command -v flock >/dev/null 2>&1 || {
  printf '[TriView Updater] ERRO: flock não encontrado.\n' >&2
  exit 1
}

mkdir -p "$STATE_ROOT"
exec 9>"$LIFECYCLE_LOCK"
if ! flock -n 9; then
  printf '[TriView Updater] ERRO: outra operação de instalação, atualização ou rollback já está em execução.\n' >&2
  exit 2
fi

explicit_cli_channel=0
dry_run=0
for argument in "$@"; do
  case "$argument" in
    --stable|--testing) explicit_cli_channel=1 ;;
    --dry-run) dry_run=1 ;;
  esac
done

forwarded_args=("$@")
if ((explicit_cli_channel == 0)) \
  && [[ -z "${TRIVIEW_UPDATE_CHANNEL:-}" ]] \
  && [[ ! -f "$CHANNEL_FILE" ]]; then
  forwarded_args=(--stable "${forwarded_args[@]}")
fi

set +e
bash "$CORE_SCRIPT" "${forwarded_args[@]}"
status=$?
set -e

((status == 0)) || exit "$status"
((dry_run == 0)) || exit 0

CURRENT_TARGET="$(readlink -f "$APP_ROOT/current" 2>/dev/null || true)"
[[ -n "$CURRENT_TARGET" && -d "$CURRENT_TARGET/scripts" ]] || {
  printf '[TriView Updater] ERRO: release ativa sem diretório de controladores.\n' >&2
  exit 1
}
ACTIVE_SCRIPTS="$CURRENT_TARGET/scripts"

for required_script in \
  update.sh \
  update-core.sh \
  stable-launch.sh \
  stable-diagnose.sh \
  stable-rollback.sh; do
  [[ -f "$ACTIVE_SCRIPTS/$required_script" ]] || {
    printf '[TriView Updater] ERRO: release ativa incompleta: %s\n' \
      "$ACTIVE_SCRIPTS/$required_script" >&2
    exit 1
  }
done

mkdir -p "$UPDATER_ROOT" "$BIN_DIR" "$APPLICATIONS_DIR"
for controller in \
  update.sh \
  update-core.sh \
  stable-launch.sh \
  stable-diagnose.sh \
  stable-rollback.sh; do
  source_controller="$ACTIVE_SCRIPTS/$controller"
  target_controller="$UPDATER_ROOT/$controller"
  if [[ "$source_controller" != "$target_controller" ]] \
    && ! cmp -s "$source_controller" "$target_controller" 2>/dev/null; then
    cp -a "$source_controller" "$target_controller"
  fi
  chmod +x "$target_controller"
done

APP_LAUNCHER="$BIN_DIR/triview-workspace"
UPDATE_LAUNCHER="$BIN_DIR/triview-workspace-update"
DIAGNOSE_LAUNCHER="$BIN_DIR/triview-workspace-diagnose"
ROLLBACK_LAUNCHER="$BIN_DIR/triview-workspace-rollback"

cat > "$APP_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$UPDATER_ROOT/stable-launch.sh" "\$@"
LAUNCHER

cat > "$UPDATE_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
set -uo pipefail
STATE_ROOT="\${XDG_STATE_HOME:-\$HOME/.local/state}/triview-workspace"
mkdir -p "\$STATE_ROOT"
timestamp="\$(date +%Y%m%d-%H%M%S)"
LOG_FILE="\$STATE_ROOT/update-\$timestamp.log"
set +e
TRIVIEW_UPDATER_WRAPPED=1 "$UPDATER_ROOT/update.sh" "\$@" 2>&1 | tee -a "\$LOG_FILE"
status=\${PIPESTATUS[0]}
set -e
printf '\n============================================================\n'
if ((status == 0)); then
  title='TriView Workspace — atualização concluída'
  text="A atualização foi concluída com sucesso.\\n\\nLog: \$LOG_FILE"
  printf 'ATUALIZAÇÃO FINALIZADA COM SUCESSO.\n'
else
  title='TriView Workspace — erro na atualização'
  text="A atualização terminou com erro (código \$status).\\n\\nLog: \$LOG_FILE"
  printf 'A ATUALIZAÇÃO TERMINOU COM ERRO (código %s).\n' "\$status"
fi
printf 'Log salvo em: %s\n' "\$LOG_FILE"
printf '============================================================\n\n'
if command -v zenity >/dev/null 2>&1 && [[ -n "\${DISPLAY:-}\${WAYLAND_DISPLAY:-}" ]]; then
  if ((status == 0)); then
    zenity --info --title="\$title" --text="\$text" --width=540 >/dev/null 2>&1 || true
  else
    zenity --error --title="\$title" --text="\$text" --width=540 >/dev/null 2>&1 || true
  fi
fi
if [[ "\${TRIVIEW_NO_PAUSE:-0}" != "1" && -t 0 ]]; then
  read -r -p 'Pressione ENTER para fechar esta janela... ' _ || true
fi
exit "\$status"
LAUNCHER

cat > "$DIAGNOSE_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$UPDATER_ROOT/stable-diagnose.sh" "\$@"
LAUNCHER

cat > "$ROLLBACK_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$UPDATER_ROOT/stable-rollback.sh" "\$@"
LAUNCHER
chmod +x \
  "$APP_LAUNCHER" \
  "$UPDATE_LAUNCHER" \
  "$DIAGNOSE_LAUNCHER" \
  "$ROLLBACK_LAUNCHER"

terminal_command() {
  local launcher="$1"
  if command -v x-terminal-emulator >/dev/null 2>&1; then
    printf '%s -e %s\n' "$(command -v x-terminal-emulator)" "$launcher"
  elif command -v gnome-terminal >/dev/null 2>&1; then
    printf '%s -- %s\n' "$(command -v gnome-terminal)" "$launcher"
  else
    printf '%s\n' "$launcher"
  fi
}

APP_DESKTOP="$APPLICATIONS_DIR/triview-workspace.desktop"
UPDATE_DESKTOP="$APPLICATIONS_DIR/triview-workspace-update.desktop"
DIAGNOSE_DESKTOP="$APPLICATIONS_DIR/triview-workspace-diagnose.desktop"
ROLLBACK_DESKTOP="$APPLICATIONS_DIR/triview-workspace-rollback.desktop"
UPDATE_EXEC="$(terminal_command "$UPDATE_LAUNCHER")"
ROLLBACK_EXEC="$(terminal_command "$ROLLBACK_LAUNCHER")"
UPDATE_TERMINAL=true
ROLLBACK_TERMINAL=true
[[ "$UPDATE_EXEC" != "$UPDATE_LAUNCHER" ]] && UPDATE_TERMINAL=false
[[ "$ROLLBACK_EXEC" != "$ROLLBACK_LAUNCHER" ]] && ROLLBACK_TERMINAL=false

cat > "$APP_DESKTOP" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TriView Workspace
Comment=Plataforma modular de áreas de trabalho
Exec=$APP_LAUNCHER
Icon=preferences-desktop-display
Terminal=false
Categories=Utility;Development;
StartupNotify=true
DESKTOP

cat > "$UPDATE_DESKTOP" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Atualizar TriView Workspace
Comment=Atualiza o TriView com backup e validação
Exec=$UPDATE_EXEC
Icon=system-software-update
Terminal=$UPDATE_TERMINAL
Categories=Utility;Development;
StartupNotify=true
DESKTOP

cat > "$DIAGNOSE_DESKTOP" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Diagnosticar TriView Workspace
Comment=Gera um pacote caixa-preta sanitizado para auditoria
Exec=$DIAGNOSE_LAUNCHER
Icon=utilities-system-monitor
Terminal=false
Categories=Utility;Development;
StartupNotify=true
DESKTOP

cat > "$ROLLBACK_DESKTOP" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Restaurar TriView Workspace
Comment=Restaura a versão anterior sem remover dados persistentes
Exec=$ROLLBACK_EXEC
Icon=edit-undo
Terminal=$ROLLBACK_TERMINAL
Categories=Utility;Development;
StartupNotify=true
DESKTOP
chmod +x \
  "$APP_DESKTOP" \
  "$UPDATE_DESKTOP" \
  "$DIAGNOSE_DESKTOP" \
  "$ROLLBACK_DESKTOP"

command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true

desktop_dirs=("$HOME/Desktop" "$HOME/Área de Trabalho" "$HOME/Área de trabalho")
if command -v xdg-user-dir >/dev/null 2>&1; then
  detected_desktop="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
  [[ -n "$detected_desktop" ]] && desktop_dirs=("$detected_desktop" "${desktop_dirs[@]}")
fi
for desktop_dir in "${desktop_dirs[@]}"; do
  [[ -d "$desktop_dir" ]] || continue
  while IFS='|' read -r source_desktop visible_name; do
    desktop_copy="$desktop_dir/$visible_name.desktop"
    cp -f "$source_desktop" "$desktop_copy"
    chmod +x "$desktop_copy"
    command -v gio >/dev/null 2>&1 \
      && gio set "$desktop_copy" metadata::trusted true >/dev/null 2>&1 || true
  done <<DESKTOP_LIST
$APP_DESKTOP|TriView Workspace
$UPDATE_DESKTOP|Atualizar TriView Workspace
$DIAGNOSE_DESKTOP|Diagnosticar TriView Workspace
$ROLLBACK_DESKTOP|Restaurar TriView Workspace
DESKTOP_LIST
done
