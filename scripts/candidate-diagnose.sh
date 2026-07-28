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

mkdir -p "$REPORT_DIR"

export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
export TRIVIEW_APP_ROOT="$APP_ROOT"
export TRIVIEW_RUNTIME_ROOT="$CURRENT_TARGET"
export TRIVIEW_RUNTIME_MODULE="$MODULE"

# runtime_observability remains the authoritative runtime event source.
# Collector inheritance chain retained for audit compatibility:
# triview_workspace.diagnostic_blackbox_xephyr extends
# triview_workspace.diagnostic_blackbox_verified, which extends
# triview_workspace.diagnostic_blackbox_shareable and
# triview_workspace.diagnostic_blackbox_final / the byte-safe event reader.
# The final collector refreshes provenance after auto-launch and resolves live
# X11 ancestry without exporting raw process arguments or private content.

show_result() {
  local title="$1"
  local message="$2"
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="$title" --text="$message" --width=540 >/dev/null 2>&1 || true
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
  package="$(python3 -m triview_workspace.diagnostic_blackbox_xephyr \
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
      "Pacote sanitizado gerado com sucesso:\n\n$package\n\nEnvie somente este arquivo ZIP para auditoria."
    open_report_location "$package"
    exit 0
  fi
  reason="Falha da sessão caixa-preta (status=$status)"
else
  export PYTHONPATH="${PYTHONPATH:-}"
  reason="Runtime ativo ausente"
fi

set +e
fallback_package="$(python3 -m triview_workspace.diagnostic_fallback_shareable \
  --output-dir "$REPORT_DIR" \
  --reason "$reason" 2>>"$APP_STATE/diagnostic-blackbox.stderr.log")"
fallback_status="$?"
set -e
fallback_package="$(printf '%s\n' "$fallback_package" | tail -n 1)"

if [[ "$fallback_status" -eq 0 && -n "$fallback_package" && -f "$fallback_package" ]]; then
  printf 'Pacote de contingência sanitizado: %s\n' "$fallback_package"
  show_result \
    "TriView — diagnóstico parcial" \
    "A sessão completa não terminou. Foi criado um pacote sanitizado de contingência:\n\n$fallback_package\n\nEle não representa PASS funcional."
  open_report_location "$fallback_package"
  exit 1
fi

show_result \
  "TriView — falha no diagnóstico" \
  "Não foi possível gerar o pacote completo nem o pacote sanitizado de contingência."
exit 1
