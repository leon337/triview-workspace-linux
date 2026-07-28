#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${1:?APP_ROOT ausente}"
DATA_ROOT="${2:?DATA_ROOT ausente}"
STATE_ROOT="${3:?STATE_ROOT ausente}"
MODULE="${4:?MODULE ausente}"
CURRENT="$APP_ROOT/current"
CURRENT_TARGET="$(readlink -f "$CURRENT" 2>/dev/null || true)"
APP_STATE="$STATE_ROOT/triview-workspace"
REPORT_DIR="$APP_STATE/diagnostics"
STAMP="$(date +%Y%m%d-%H%M%S)"
FALLBACK_REPORT="$REPORT_DIR/triview-diagnostic-$STAMP-fallback.txt"
PROVENANCE="$APP_STATE/runtime-provenance.json"
RUNTIME_EVENTS="$APP_STATE/runtime-events.jsonl"

mkdir -p "$REPORT_DIR"

export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
export TRIVIEW_APP_ROOT="$APP_ROOT"
export TRIVIEW_RUNTIME_ROOT="$CURRENT_TARGET"
export TRIVIEW_RUNTIME_MODULE="$MODULE"

# Compatibility contract: runtime_observability remains the provenance/event
# source used by the interactive black-box collector and the snapshot fallback.

show_result() {
  local title="$1"
  local message="$2"
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="$title" --text="$message" --width=520 >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "$title" "$message" >/dev/null 2>&1 || true
  fi
}

open_report_location() {
  local path="$1"
  local directory
  directory="$(dirname "$path")"
  if command -v xdg-open >/dev/null 2>&1; then
    nohup xdg-open "$directory" >/dev/null 2>&1 &
  elif command -v thunar >/dev/null 2>&1; then
    nohup thunar "$directory" >/dev/null 2>&1 &
  fi
}

if [[ -n "$CURRENT_TARGET" && -d "$CURRENT_TARGET" ]]; then
  METADATA="$CURRENT_TARGET/candidate-release.json"
  RESOLVED_SHA="$(python3 - "$METADATA" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("")
else:
    print(payload.get("resolved_sha", ""))
PY
  )"
  export TRIVIEW_RUNTIME_SHA="$RESOLVED_SHA"
  export PYTHONPATH="$CURRENT_TARGET/src${PYTHONPATH:+:$PYTHONPATH}"
  cd "$CURRENT_TARGET"

  set +e
  package="$(python3 -m triview_workspace.diagnostic_blackbox_rc \
    --output-dir "$REPORT_DIR" \
    --timeout-seconds "${TRIVIEW_DIAGNOSTIC_TIMEOUT_SECONDS:-900}" \
    --auto-launch \
    --auto-stop-on-application-exit 2>>"$APP_STATE/diagnostic-blackbox.stderr.log")"
  status="$?"
  set -e

  package="$(printf '%s\n' "$package" | tail -n 1)"
  if [[ "$status" -eq 0 && -n "$package" && -f "$package" ]]; then
    printf 'Pacote de diagnóstico: %s\n' "$package"
    show_result \
      "TriView — diagnóstico concluído" \
      "Pacote gerado com sucesso:\n\n$package\n\nEnvie somente este arquivo ZIP para auditoria."
    open_report_location "$package"
    exit 0
  fi
  output="Falha da sessão caixa-preta (status=$status, saída=$package)"
else
  output="Runtime ativo ausente: $CURRENT"
fi

# Fallback: preserve the existing non-destructive snapshot even if the new
# interactive black-box collector cannot start in the local graphical session.
{
  printf 'TRIVIEW WORKSPACE — DIAGNÓSTICO DE CONTINGÊNCIA\n'
  printf '================================================\n'
  printf 'Gerado em: %s\n' "$(date --iso-8601=seconds)"
  printf 'APP_ROOT: %s\n' "$APP_ROOT"
  printf 'CURRENT: %s\n' "$CURRENT"
  printf 'CURRENT_TARGET: %s\n' "$CURRENT_TARGET"
  printf 'DATA_ROOT: %s\n' "$DATA_ROOT"
  printf 'STATE_ROOT: %s\n' "$STATE_ROOT"
  printf 'MODULE: %s\n' "$MODULE"
  printf 'DISPLAY: %s\n' "${DISPLAY:-}"
  printf 'XDG_SESSION_TYPE: %s\n' "${XDG_SESSION_TYPE:-}"
  printf 'Falha do diagnóstico caixa-preta: %s\n\n' "$output"

  printf '[links]\n'
  ls -la "$APP_ROOT" 2>&1 || true
  printf '\n[metadados]\n'
  if [[ -n "$CURRENT_TARGET" && -f "$CURRENT_TARGET/candidate-release.json" ]]; then
    cat "$CURRENT_TARGET/candidate-release.json"
  else
    printf 'candidate-release.json ausente\n'
  fi
  printf '\n[processos TriView/Chromium]\n'
  ps -eo pid,ppid,pgid,lstart,args \
    | grep -E 'triview_workspace|browser-profiles|brave|chromium' \
    | grep -v grep || true
  printf '\n[xdotool]\n'
  command -v xdotool || true
  xdotool version 2>&1 || true
  printf '\n[xinput]\n'
  command -v xinput || true
  printf '\n[xwininfo root tree]\n'
  xwininfo -root -tree 2>&1 || true
  printf '\n[launcher log]\n'
  tail -n 300 "$APP_STATE/launcher.log" 2>&1 || true
  printf '\n[runtime provenance]\n'
  cat "$PROVENANCE" 2>&1 || true
  printf '\nÚLTIMOS EVENTOS DO RUNTIME\n'
  printf '%s\n' '--------------------------------------------------------'
  tail -n 500 "$RUNTIME_EVENTS" 2>&1 || true
  printf '\n[diagnostic blackbox stderr]\n'
  tail -n 300 "$APP_STATE/diagnostic-blackbox.stderr.log" 2>&1 || true
  printf '\n[app stderr]\n'
  tail -n 300 "$APP_STATE/app.stderr.log" 2>&1 || true
} >"$FALLBACK_REPORT"

printf 'Relatório de contingência: %s\n' "$FALLBACK_REPORT"
show_result \
  "TriView — diagnóstico de contingência" \
  "A sessão caixa-preta não pôde ser concluída. Foi criado um relatório de contingência:\n\n$FALLBACK_REPORT"
if command -v xed >/dev/null 2>&1; then
  nohup xed "$FALLBACK_REPORT" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
  nohup xdg-open "$FALLBACK_REPORT" >/dev/null 2>&1 &
fi
exit 1
