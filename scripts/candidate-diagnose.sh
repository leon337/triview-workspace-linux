#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${1:?APP_ROOT ausente}"
DATA_ROOT="${2:?DATA_ROOT ausente}"
STATE_ROOT="${3:?STATE_ROOT ausente}"
MODULE="${4:?MODULE ausente}"
CURRENT="$APP_ROOT/current"
CURRENT_TARGET="$(readlink -f "$CURRENT" 2>/dev/null || true)"
REPORT_DIR="$STATE_ROOT/triview-workspace/diagnostics"
STAMP="$(date +%Y%m%d-%H%M%S)"
FALLBACK_REPORT="$REPORT_DIR/triview-diagnostic-$STAMP-fallback.txt"

mkdir -p "$REPORT_DIR"

export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
export TRIVIEW_RUNTIME_ROOT="$CURRENT_TARGET"
export TRIVIEW_RUNTIME_MODULE="$MODULE"

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
  output="$(python3 -m triview_workspace.runtime_observability \
    --report --output-dir "$REPORT_DIR" 2>&1)"
  status="$?"
  set -e
  if [[ "$status" -eq 0 ]]; then
    TEXT_REPORT="$(printf '%s\n' "$output" | sed -n '1p')"
    JSON_REPORT="$(printf '%s\n' "$output" | sed -n '2p')"
    printf 'Relatório TXT: %s\nRelatório JSON: %s\n' "$TEXT_REPORT" "$JSON_REPORT"
    if command -v xed >/dev/null 2>&1; then
      nohup xed "$TEXT_REPORT" >/dev/null 2>&1 &
    elif command -v xdg-open >/dev/null 2>&1; then
      nohup xdg-open "$TEXT_REPORT" >/dev/null 2>&1 &
    fi
    exit 0
  fi
else
  output="Runtime ativo ausente: $CURRENT"
fi

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
  printf 'Falha do diagnóstico Python: %s\n\n' "$output"

  printf '[links]\n'
  ls -la "$APP_ROOT" 2>&1 || true
  printf '\n[metadados]\n'
  if [[ -n "$CURRENT_TARGET" && -f "$CURRENT_TARGET/candidate-release.json" ]]; then
    cat "$CURRENT_TARGET/candidate-release.json"
  else
    printf 'candidate-release.json ausente\n'
  fi
  printf '\n[processos TriView/Chromium]\n'
  ps -eo pid,ppid,pgid,lstart,args | grep -E 'triview_workspace|browser-profiles|brave|chromium' | grep -v grep || true
  printf '\n[xdotool]\n'
  command -v xdotool || true
  xdotool version 2>&1 || true
  printf '\n[xwininfo root tree]\n'
  xwininfo -root -tree 2>&1 || true
  printf '\n[launcher log]\n'
  tail -n 300 "$STATE_ROOT/triview-workspace/launcher.log" 2>&1 || true
  printf '\n[runtime events]\n'
  tail -n 500 "$STATE_ROOT/triview-workspace/runtime-events.jsonl" 2>&1 || true
  printf '\n[stderr]\n'
  tail -n 300 "$STATE_ROOT/triview-workspace/app.stderr.log" 2>&1 || true
} >"$FALLBACK_REPORT"

printf 'Relatório de contingência: %s\n' "$FALLBACK_REPORT"
if command -v xed >/dev/null 2>&1; then
  nohup xed "$FALLBACK_REPORT" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
  nohup xdg-open "$FALLBACK_REPORT" >/dev/null 2>&1 &
fi
