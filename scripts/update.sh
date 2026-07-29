#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${TRIVIEW_REPO:-leon337/triview-workspace-linux}"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
BACKUP_ROOT="${TRIVIEW_BACKUP_ROOT:-$HOME/.local/share/triview-workspace-backups}"
DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/triview-workspace"
CATALOG_FILE="${TRIVIEW_DATA_FILE:-$DATA_ROOT/triview-workspace/workspaces.json}"
CURRENT_LINK="$APP_ROOT/current"
UPDATER_ROOT="$APP_ROOT/updater"
CHANNEL_FILE="$APP_ROOT/UPDATE_CHANNEL"
ACTIVE_CANDIDATE_FILE="$APP_ROOT/ACTIVE-CANDIDATE.json"
TEST_MANIFEST_URL="${TRIVIEW_TEST_MANIFEST_URL:-https://raw.githubusercontent.com/$REPO/main/config/update-channels/testing.json}"
DRY_RUN=0
CHANNEL_OVERRIDE=""
TMP_DIR=""
RESULT_SUMMARY="Atualização encerrada."

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --stable) CHANNEL_OVERRIDE="stable"; shift ;;
    --testing) CHANNEL_OVERRIDE="testing"; shift ;;
    --help|-h)
      printf 'Uso: update.sh [--dry-run] [--stable|--testing]\n'
      exit 0
      ;;
    *) printf 'Opção desconhecida: %s\n' "$1" >&2; exit 2 ;;
  esac
done

log() { printf '[TriView Updater] %s\n' "$*"; }
fail() { RESULT_SUMMARY="$*"; log "ERRO: $*" >&2; exit 1; }
run() {
  if ((DRY_RUN)); then
    printf '[DRY-RUN]'; printf ' %q' "$@"; printf '\n'
  else
    "$@"
  fi
}

show_direct_result() {
  local status="$1"
  local title text icon

  ((DRY_RUN)) && return 0
  [[ "${TRIVIEW_UPDATER_WRAPPED:-0}" == "1" ]] && return 0
  [[ "${TRIVIEW_NO_RESULT_UI:-0}" == "1" ]] && return 0

  if ((status == 0)); then
    title="TriView Workspace — atualização concluída"
    text="A atualização foi concluída com sucesso.\n\n$RESULT_SUMMARY"
    icon="--info"
  else
    title="TriView Workspace — erro na atualização"
    text="A atualização terminou com erro (código $status).\n\n$RESULT_SUMMARY"
    icon="--error"
  fi

  printf '\n============================================================\n'
  printf '%s\n' "$title"
  printf '%b\n' "$text"
  printf '============================================================\n\n'

  if command -v zenity >/dev/null 2>&1 \
    && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    zenity "$icon" --title="$title" --text="$text" --width=520 >/dev/null 2>&1 || true
    return 0
  fi

  if [[ -t 0 ]]; then
    read -r -p 'Pressione ENTER para fechar esta janela... ' _ || true
  elif [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    sleep 20
  fi
}

finish() {
  local status=$?
  trap - EXIT
  [[ -n "$TMP_DIR" ]] && rm -rf "$TMP_DIR"
  show_direct_result "$status"
  exit "$status"
}
trap finish EXIT

for command in curl tar python3; do
  command -v "$command" >/dev/null 2>&1 || fail "$command não encontrado."
done

resolve_channel() {
  if [[ -n "$CHANNEL_OVERRIDE" ]]; then
    printf '%s\n' "$CHANNEL_OVERRIDE"
  elif [[ -n "${TRIVIEW_UPDATE_CHANNEL:-}" ]]; then
    printf '%s\n' "$TRIVIEW_UPDATE_CHANNEL"
  elif [[ -f "$CHANNEL_FILE" ]]; then
    tr -d '[:space:]' < "$CHANNEL_FILE"
    printf '\n'
  else
    printf 'testing\n'
  fi
}

CHANNEL="$(resolve_channel)"
[[ "$CHANNEL" == "stable" || "$CHANNEL" == "testing" ]] \
  || fail "Canal inválido: $CHANNEL"

write_update_desktop_entry() {
  local output_file="$1"
  local launcher="$2"
  local terminal_exec terminal_flag

  if command -v x-terminal-emulator >/dev/null 2>&1; then
    terminal_exec="$(command -v x-terminal-emulator) -e $launcher"
    terminal_flag="false"
  elif command -v gnome-terminal >/dev/null 2>&1; then
    terminal_exec="$(command -v gnome-terminal) -- $launcher"
    terminal_flag="false"
  else
    terminal_exec="$launcher"
    terminal_flag="true"
  fi

  cat > "$output_file" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Atualizar TriView Workspace
Comment=Atualiza o TriView Workspace com backup e validação
Exec=$terminal_exec
Icon=system-software-update
Terminal=$terminal_flag
Categories=Utility;Development;
StartupNotify=true
DESKTOP
  chmod +x "$output_file"
}

refresh_desktop_copies() {
  local source_desktop="$1"
  local detected=""
  local directory file canonical
  local -a desktop_dirs=()

  if command -v xdg-user-dir >/dev/null 2>&1; then
    detected="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    [[ -n "$detected" ]] && desktop_dirs+=("$detected")
  fi
  desktop_dirs+=("$HOME/Desktop" "$HOME/Área de Trabalho" "$HOME/Área de trabalho")

  for directory in "${desktop_dirs[@]}"; do
    [[ -d "$directory" ]] || continue
    canonical="$directory/Atualizar TriView Workspace.desktop"
    cp -f "$source_desktop" "$canonical"
    chmod +x "$canonical"
    command -v gio >/dev/null 2>&1 \
      && gio set "$canonical" metadata::trusted true >/dev/null 2>&1 || true

    while IFS= read -r -d '' file; do
      if grep -Eq '^Name=Atualizar TriView Workspace$|triview-workspace.*update|scripts/update\.sh' "$file" 2>/dev/null; then
        cp -f "$source_desktop" "$file"
        chmod +x "$file"
        command -v gio >/dev/null 2>&1 \
          && gio set "$file" metadata::trusted true >/dev/null 2>&1 || true
      fi
    done < <(find "$directory" -maxdepth 1 -type f -name '*.desktop' -print0 2>/dev/null)
  done
}

install_persistent_updater() {
  local source_script target_script launcher applications_dir desktop
  source_script="$(readlink -f "${BASH_SOURCE[0]}")"
  target_script="$UPDATER_ROOT/update.sh"
  launcher="$HOME/.local/bin/triview-workspace-update"
  applications_dir="$HOME/.local/share/applications"
  desktop="$applications_dir/triview-workspace-update.desktop"

  run mkdir -p "$UPDATER_ROOT" "$HOME/.local/bin" "$applications_dir" "$STATE_ROOT"
  if ((DRY_RUN)); then
    log "O controlador persistente seria instalado em $target_script"
    log "O atalho antigo da Área de Trabalho seria substituído."
    log "O resultado seria exibido em janela gráfica e salvo em log."
    return
  fi

  if [[ "$source_script" != "$target_script" ]] \
    && ! cmp -s "$source_script" "$target_script" 2>/dev/null; then
    cp -a "$source_script" "$target_script"
  fi
  chmod +x "$target_script"

  cat > "$launcher" <<LAUNCHER
#!/usr/bin/env bash
set -uo pipefail
STATE_ROOT="\${XDG_STATE_HOME:-\$HOME/.local/state}/triview-workspace"
mkdir -p "\$STATE_ROOT"
timestamp="\$(date +%Y%m%d-%H%M%S)"
LOG_FILE="\$STATE_ROOT/update-\$timestamp.log"

set +e
TRIVIEW_UPDATER_WRAPPED=1 "$target_script" "\$@" 2>&1 | tee -a "\$LOG_FILE"
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
    zenity --info --title="\$title" --text="\$text" --width=520 >/dev/null 2>&1 || true
  else
    zenity --error --title="\$title" --text="\$text" --width=520 >/dev/null 2>&1 || true
  fi
fi

if [[ "\${TRIVIEW_NO_PAUSE:-0}" != "1" ]]; then
  if [[ -t 0 ]]; then
    read -r -p 'Pressione ENTER para fechar esta janela... ' _ || true
  elif [[ -n "\${DISPLAY:-}\${WAYLAND_DISPLAY:-}" ]]; then
    sleep 20
  fi
fi
exit "\$status"
LAUNCHER
  chmod +x "$launcher"

  write_update_desktop_entry "$desktop" "$launcher"
  update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
  refresh_desktop_copies "$desktop"
}

read_testing_manifest() {
  local manifest_file="$1"
  python3 - "$manifest_file" <<'PY'
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
required = {
    "schema_version",
    "channel",
    "enabled",
    "candidate_id",
    "version",
    "ref",
    "module",
    "status",
}
missing = sorted(required.difference(data))
if missing:
    raise SystemExit(f"Manifesto incompleto: {', '.join(missing)}")
if data["schema_version"] != 1:
    raise SystemExit("schema_version incompatível")
if data["channel"] != "testing":
    raise SystemExit("canal do manifesto incompatível")
if data["enabled"] is not True:
    raise SystemExit("canal de testes bloqueado")
if not re.fullmatch(r"LEA-[0-9]{3}", str(data["candidate_id"])):
    raise SystemExit("candidate_id inválido")
if not re.fullmatch(r"[0-9a-f]{40}", str(data["ref"])):
    raise SystemExit("ref precisa ser um commit SHA completo")
if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", str(data["version"])):
    raise SystemExit("versão inválida")
if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", str(data["module"])):
    raise SystemExit("módulo inválido")
for key in ("candidate_id", "version", "ref", "module", "status"):
    print(data[key])
PY
}

mkdir -p "$APP_ROOT/releases" "$BACKUP_ROOT" "$STATE_ROOT"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="$BACKUP_ROOT/update-$timestamp"
TMP_DIR="$(mktemp -d)"

TARGET_ID="stable"
EXPECTED_VERSION=""
TARGET_REF=""
TARGET_MODULE="triview_workspace.cli"
TARGET_STATUS="stable"
archive_url=""

if [[ "$CHANNEL" == "testing" ]]; then
  manifest_file="$TMP_DIR/testing.json"
  if [[ -n "${TRIVIEW_TEST_MANIFEST_FILE:-}" ]]; then
    cp -a "$TRIVIEW_TEST_MANIFEST_FILE" "$manifest_file"
  else
    log "Consultando o canal controlado de testes..."
    curl -fsSL "$TEST_MANIFEST_URL" -o "$manifest_file" \
      || fail "Não foi possível consultar o canal de testes."
  fi
  mapfile -t manifest_values < <(read_testing_manifest "$manifest_file") \
    || fail "Manifesto do canal de testes inválido."
  ((${#manifest_values[@]} == 5)) || fail "Manifesto do canal de testes incompleto."
  TARGET_ID="${manifest_values[0]}"
  EXPECTED_VERSION="${manifest_values[1]}"
  TARGET_REF="${manifest_values[2]}"
  TARGET_MODULE="${manifest_values[3]}"
  TARGET_STATUS="${manifest_values[4]}"
  archive_url="https://github.com/$REPO/archive/$TARGET_REF.tar.gz"
  log "Candidato autorizado: $TARGET_ID — versão $EXPECTED_VERSION"
  log "Commit fixado: $TARGET_REF"

  if [[ -f "$ACTIVE_CANDIDATE_FILE" ]] && python3 - "$ACTIVE_CANDIDATE_FILE" "$TARGET_REF" <<'PY'
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, ValueError):
    raise SystemExit(1)
raise SystemExit(0 if data.get("ref") == sys.argv[2] else 1)
PY
  then
    install_persistent_updater
    RESULT_SUMMARY="$TARGET_ID já está ativo. O atalho foi corrigido."
    log "$TARGET_ID já está ativo neste computador. Nenhuma reinstalação foi feita."
    exit 0
  fi
else
  release_api="https://api.github.com/repos/$REPO/releases/latest"
  if archive_url="$(curl -fsSL "$release_api" 2>/dev/null | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("tarball_url", ""))' 2>/dev/null)" \
    && [[ -n "$archive_url" ]]; then
    log "Usando a release estável mais recente."
  else
    archive_url="https://github.com/$REPO/archive/refs/heads/main.tar.gz"
    log "Ainda não há release estável; usando a branch main."
  fi
fi

if [[ -L "$CURRENT_LINK" ]]; then
  current_target="$(readlink -f "$CURRENT_LINK")"
  run mkdir -p "$backup_dir"
  if ((DRY_RUN)); then
    log "A versão atual seria copiada para $backup_dir/current"
  else
    cp -a "$current_target" "$backup_dir/current"
  fi
fi

if [[ -f "$CATALOG_FILE" ]]; then
  run mkdir -p "$backup_dir"
  if ((DRY_RUN)); then
    log "O catálogo seria copiado para $backup_dir/workspaces.json"
  else
    cp -a "$CATALOG_FILE" "$backup_dir/workspaces.json"
  fi
fi

log "Baixando atualização do canal $CHANNEL..."
run curl -fL "$archive_url" -o "$TMP_DIR/source.tar.gz"
run mkdir -p "$TMP_DIR/extracted"
run tar -xzf "$TMP_DIR/source.tar.gz" -C "$TMP_DIR/extracted" --strip-components=1

if ((DRY_RUN)); then
  install_persistent_updater
  log "A validação, instalação e troca atômica seriam executadas agora."
  exit 0
fi

[[ -f "$TMP_DIR/extracted/pyproject.toml" ]] || fail "Pacote baixado inválido."
[[ -d "$TMP_DIR/extracted/src/triview_workspace" ]] || fail "Código da aplicação ausente."
python3 -m compileall -q "$TMP_DIR/extracted/src"
version="$(python3 - "$TMP_DIR/extracted/pyproject.toml" <<'PY'
from pathlib import Path
import re
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
if not match:
    raise SystemExit("versão ausente")
print(match.group(1))
PY
)"

if [[ -n "$EXPECTED_VERSION" && "$version" != "$EXPECTED_VERSION" ]]; then
  fail "Versão recebida $version difere da versão autorizada $EXPECTED_VERSION."
fi

release_suffix="$(printf '%s' "$TARGET_ID" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9._-')"
release_dir="$APP_ROOT/releases/$version-$release_suffix-$timestamp"
mkdir -p "$release_dir"
cp -a "$TMP_DIR/extracted/." "$release_dir/"

export PYTHONPATH="$release_dir/src"
cd "$release_dir"
python3 -m triview_workspace.cli \
  --diagnostic \
  --workspace "$release_dir/config/workspaces/three-mobile.json" \
  --data-file "$TMP_DIR/diagnostic-workspaces.json" >/dev/null
python3 - "$TARGET_MODULE" <<'PY'
import importlib
import sys

module = importlib.import_module(sys.argv[1])
if not callable(getattr(module, "main", None)):
    raise SystemExit("o módulo gráfico não possui main()")
PY

install_persistent_updater

temp_link="$APP_ROOT/.current-$timestamp"
ln -s "$release_dir" "$temp_link"
mv -Tf "$temp_link" "$CURRENT_LINK"
printf '%s\n' "$version" > "$APP_ROOT/VERSION"
printf '%s\n' "$CHANNEL" > "$CHANNEL_FILE"

BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="$HOME/.local/share/applications"
mkdir -p "$BIN_DIR" "$APPLICATIONS_DIR"
cat > "$BIN_DIR/triview-workspace" <<LAUNCHER
#!/usr/bin/env bash
set -Eeuo pipefail
APP_ROOT="$APP_ROOT"
CURRENT="\$APP_ROOT/current"
export PYTHONPATH="\$CURRENT/src\${PYTHONPATH:+:\$PYTHONPATH}"
cd "\$CURRENT"
exec python3 -m "$TARGET_MODULE" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/triview-workspace"
cat > "$APPLICATIONS_DIR/triview-workspace.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=TriView Workspace
Comment=Plataforma modular de áreas de trabalho
Exec=$BIN_DIR/triview-workspace
Icon=preferences-desktop-display
Terminal=false
Categories=Utility;Development;
StartupNotify=true
DESKTOP
chmod +x "$APPLICATIONS_DIR/triview-workspace.desktop"
update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true

python3 - "$ACTIVE_CANDIDATE_FILE" "$CHANNEL" "$TARGET_ID" "$version" "$TARGET_REF" "$TARGET_MODULE" "$TARGET_STATUS" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "channel": sys.argv[2],
    "candidate_id": sys.argv[3],
    "version": sys.argv[4],
    "ref": sys.argv[5],
    "module": sys.argv[6],
    "status": sys.argv[7],
}
temporary = path.with_suffix(".tmp")
temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
temporary.replace(path)
PY

RESULT_SUMMARY="Versão ativa: $version. Atalho da Área de Trabalho corrigido."
log "Atualização concluída. Canal: $CHANNEL"
log "Versão ativa: $version"
if [[ "$CHANNEL" == "testing" ]]; then
  log "Candidato ativo: $TARGET_ID"
fi
log "Catálogo persistente preservado em: $CATALOG_FILE"
log "Backup: $backup_dir"

if ! command -v xdotool >/dev/null 2>&1; then
  log "AVISO: xdotool não foi encontrado; a incorporação X11 ficará indisponível."
  log "Instale no Linux Mint/Ubuntu com: sudo apt install xdotool"
fi
