#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_ROOT="$(readlink -f "$SCRIPT_DIR/..")"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
CURRENT_LINK="$APP_ROOT/current"
CHANNEL_FILE="$APP_ROOT/UPDATE_CHANNEL"
UPDATER_ROOT="$APP_ROOT/updater"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/triview-workspace"
BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="$HOME/.local/share/applications"
LIFECYCLE_LOCK="$STATE_ROOT/lifecycle.lock"
APP_LOCK="$STATE_ROOT/app.lock"

CURRENT_TARGET="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
ACTIVE_CHANNEL="$(tr -d '[:space:]' < "$CHANNEL_FILE" 2>/dev/null || true)"

# This handoff exists specifically for upgrades initiated by the immutable
# 1.0.0a2 controller. It may run only from the release that is already active.
[[ -n "$CURRENT_TARGET" && "$CURRENT_TARGET" == "$RELEASE_ROOT" ]] || exit 0
[[ "$ACTIVE_CHANNEL" == "stable" ]] || exit 0

for command in flock python3; do
  command -v "$command" >/dev/null 2>&1 || {
    printf '[TriView Adoption] ERRO: %s não encontrado.\n' "$command" >&2
    exit 1
  }
done
for controller in \
  update.sh \
  update-core.sh \
  stable-launch.sh \
  stable-diagnose.sh \
  stable-rollback.sh; do
  [[ -f "$SCRIPT_DIR/$controller" ]] || {
    printf '[TriView Adoption] ERRO: release ativa incompleta: %s\n' \
      "$SCRIPT_DIR/$controller" >&2
    exit 1
  }
done

mkdir -p "$STATE_ROOT"
exec 9>"$LIFECYCLE_LOCK"
if ! flock -n 9; then
  printf '[TriView Adoption] ERRO: outra operação de ciclo de vida está em execução.\n' >&2
  exit 2
fi
exec 8>"$APP_LOCK"
if ! flock -n 8; then
  printf '[TriView Adoption] ERRO: outra instância do TriView já está em execução.\n' >&2
  exit 3
fi

mkdir -p "$UPDATER_ROOT" "$BIN_DIR" "$APPLICATIONS_DIR"

atomic_copy() {
  local source="$1"
  local target="$2"
  local temporary
  temporary="$(mktemp "$(dirname "$target")/.triview-adopt.XXXXXX")"
  cp -a "$source" "$temporary"
  chmod +x "$temporary"
  mv -f "$temporary" "$target"
}

atomic_write() {
  local target="$1"
  local temporary
  temporary="$(mktemp "$(dirname "$target")/.triview-adopt.XXXXXX")"
  cat > "$temporary"
  chmod +x "$temporary"
  mv -f "$temporary" "$target"
}

for controller in \
  update.sh \
  update-core.sh \
  stable-launch.sh \
  stable-diagnose.sh \
  stable-rollback.sh; do
  atomic_copy "$SCRIPT_DIR/$controller" "$UPDATER_ROOT/$controller"
done

APP_LAUNCHER="$BIN_DIR/triview-workspace"
UPDATE_LAUNCHER="$BIN_DIR/triview-workspace-update"
DIAGNOSE_LAUNCHER="$BIN_DIR/triview-workspace-diagnose"
ROLLBACK_LAUNCHER="$BIN_DIR/triview-workspace-rollback"

atomic_write "$APP_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$UPDATER_ROOT/stable-launch.sh" "\$@"
LAUNCHER

atomic_write "$UPDATE_LAUNCHER" <<LAUNCHER
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
printf '\nLog salvo em: %s\n' "\$LOG_FILE"
exit "\$status"
LAUNCHER

atomic_write "$DIAGNOSE_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$UPDATER_ROOT/stable-diagnose.sh" "\$@"
LAUNCHER

atomic_write "$ROLLBACK_LAUNCHER" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
exec "$UPDATER_ROOT/stable-rollback.sh" "\$@"
LAUNCHER

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

UPDATE_EXEC="$(terminal_command "$UPDATE_LAUNCHER")"
ROLLBACK_EXEC="$(terminal_command "$ROLLBACK_LAUNCHER")"
UPDATE_TERMINAL=true
ROLLBACK_TERMINAL=true
[[ "$UPDATE_EXEC" != "$UPDATE_LAUNCHER" ]] && UPDATE_TERMINAL=false
[[ "$ROLLBACK_EXEC" != "$ROLLBACK_LAUNCHER" ]] && ROLLBACK_TERMINAL=false

APP_DESKTOP="$APPLICATIONS_DIR/triview-workspace.desktop"
UPDATE_DESKTOP="$APPLICATIONS_DIR/triview-workspace-update.desktop"
DIAGNOSE_DESKTOP="$APPLICATIONS_DIR/triview-workspace-diagnose.desktop"
ROLLBACK_DESKTOP="$APPLICATIONS_DIR/triview-workspace-rollback.desktop"

atomic_write "$APP_DESKTOP" <<DESKTOP
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

atomic_write "$UPDATE_DESKTOP" <<DESKTOP
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

atomic_write "$DIAGNOSE_DESKTOP" <<DESKTOP
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

atomic_write "$ROLLBACK_DESKTOP" <<DESKTOP
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
    atomic_copy "$source_desktop" "$desktop_dir/$visible_name.desktop"
    command -v gio >/dev/null 2>&1 \
      && gio set "$desktop_dir/$visible_name.desktop" metadata::trusted true >/dev/null 2>&1 || true
  done <<DESKTOP_LIST
$APP_DESKTOP|TriView Workspace
$UPDATE_DESKTOP|Atualizar TriView Workspace
$DIAGNOSE_DESKTOP|Diagnosticar TriView Workspace
$ROLLBACK_DESKTOP|Restaurar TriView Workspace
DESKTOP_LIST
done

VERSION="$(tr -d '[:space:]' < "$APP_ROOT/VERSION" 2>/dev/null || true)"
REPORT_DIR="$STATE_ROOT/stable-adoption"
mkdir -p "$REPORT_DIR"
python3 - "$REPORT_DIR/latest.json" "$RELEASE_ROOT" "$VERSION" <<'PY'
from __future__ import annotations

import json
import pathlib
import sys
from datetime import datetime, timezone

path = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "status": "adopted",
    "release_root": sys.argv[2],
    "version": sys.argv[3],
    "controllers": 5,
    "commands": 4,
    "shortcuts": 4,
    "adopted_at": datetime.now(timezone.utc).isoformat(),
}
temporary = path.with_suffix(".tmp")
temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
temporary.replace(path)
PY

printf '[TriView Adoption] Controladores e atalhos da release ativa foram adotados.\n'
