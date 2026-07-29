#!/usr/bin/env bash
set -Eeuo pipefail

EXECUTING_PATH="$(readlink -f "${BASH_SOURCE[0]}")"

# Bash pode ler este arquivo progressivamente. O núcleo legado substitui
# updater/update.sh durante a atualização; por isso o controlador precisa
# continuar a partir de uma cópia imutável antes de chamar o núcleo.
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
ROLLBACK_SOURCE="$SCRIPT_DIR/stable-rollback.sh"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
CHANNEL_FILE="$APP_ROOT/UPDATE_CHANNEL"
UPDATER_ROOT="$APP_ROOT/updater"
TARGET_WRAPPER="$UPDATER_ROOT/update.sh"
TARGET_CORE="$UPDATER_ROOT/update-core.sh"
TARGET_ROLLBACK="$UPDATER_ROOT/stable-rollback.sh"

cleanup() {
  rm -f "$CONTROLLER_SOURCE" || true
  return 0
}
trap cleanup EXIT

[[ -f "$CORE_SCRIPT" ]] || {
  printf '[TriView Updater] ERRO: núcleo do atualizador ausente: %s\n' "$CORE_SCRIPT" >&2
  exit 1
}
[[ -f "$ROLLBACK_SOURCE" ]] || {
  printf '[TriView Updater] ERRO: rollback estável ausente: %s\n' "$ROLLBACK_SOURCE" >&2
  exit 1
}

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

# O núcleo instala a si próprio em updater/update.sh. Restauramos o
# controlador a partir da cópia imutável e mantemos núcleo e rollback ao lado.
mkdir -p "$UPDATER_ROOT"
if [[ "$CORE_SCRIPT" != "$TARGET_CORE" ]] && ! cmp -s "$CORE_SCRIPT" "$TARGET_CORE"; then
  cp -a "$CORE_SCRIPT" "$TARGET_CORE"
fi
if ! cmp -s "$CONTROLLER_SOURCE" "$TARGET_WRAPPER"; then
  cp -a "$CONTROLLER_SOURCE" "$TARGET_WRAPPER"
fi
if [[ "$ROLLBACK_SOURCE" != "$TARGET_ROLLBACK" ]] && ! cmp -s "$ROLLBACK_SOURCE" "$TARGET_ROLLBACK"; then
  cp -a "$ROLLBACK_SOURCE" "$TARGET_ROLLBACK"
fi
chmod +x "$TARGET_WRAPPER" "$TARGET_CORE" "$TARGET_ROLLBACK"

ROLLBACK_LAUNCHER="$HOME/.local/bin/triview-workspace-rollback"
APPLICATIONS_DIR="$HOME/.local/share/applications"
ROLLBACK_DESKTOP="$APPLICATIONS_DIR/triview-workspace-rollback.desktop"
mkdir -p "$HOME/.local/bin" "$APPLICATIONS_DIR"

cat > "$ROLLBACK_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$TARGET_ROLLBACK" "\$@"
LAUNCHER
chmod +x "$ROLLBACK_LAUNCHER"

terminal_flag="true"
rollback_exec="$ROLLBACK_LAUNCHER"
if command -v x-terminal-emulator >/dev/null 2>&1; then
  rollback_exec="$(command -v x-terminal-emulator) -e $ROLLBACK_LAUNCHER"
  terminal_flag="false"
elif command -v gnome-terminal >/dev/null 2>&1; then
  rollback_exec="$(command -v gnome-terminal) -- $ROLLBACK_LAUNCHER"
  terminal_flag="false"
fi

cat > "$ROLLBACK_DESKTOP" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Restaurar TriView Workspace
Comment=Restaura a versão anterior do TriView sem remover dados persistentes
Exec=$rollback_exec
Icon=edit-undo
Terminal=$terminal_flag
Categories=Utility;Development;
StartupNotify=true
DESKTOP
chmod +x "$ROLLBACK_DESKTOP"
command -v update-desktop-database >/dev/null 2>&1 \
  && update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true

desktop_dirs=("$HOME/Desktop" "$HOME/Área de Trabalho" "$HOME/Área de trabalho")
if command -v xdg-user-dir >/dev/null 2>&1; then
  detected_desktop="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
  [[ -n "$detected_desktop" ]] && desktop_dirs=("$detected_desktop" "${desktop_dirs[@]}")
fi
for desktop_dir in "${desktop_dirs[@]}"; do
  [[ -d "$desktop_dir" ]] || continue
  desktop_copy="$desktop_dir/Restaurar TriView Workspace.desktop"
  cp -f "$ROLLBACK_DESKTOP" "$desktop_copy"
  chmod +x "$desktop_copy"
  command -v gio >/dev/null 2>&1 \
    && gio set "$desktop_copy" metadata::trusted true >/dev/null 2>&1 || true
done
