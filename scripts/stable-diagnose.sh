#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}"
MODULE="${TRIVIEW_STABLE_MODULE:-triview_workspace.cli}"
CURRENT="$APP_ROOT/current"
CURRENT_TARGET="$(readlink -f "$CURRENT" 2>/dev/null || true)"
APP_STATE="$STATE_ROOT/triview-workspace"
REPORT_DIR="$APP_STATE/diagnostics"
APP_LOCK="$APP_STATE/app.lock"

mkdir -p "$REPORT_DIR"

export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
export TRIVIEW_APP_ROOT="$APP_ROOT"
export TRIVIEW_RUNTIME_ROOT="$CURRENT_TARGET"
export TRIVIEW_RUNTIME_MODULE="$MODULE"

show_result() {
  local title="$1"
  local message="$2"
  if command -v zenity >/dev/null 2>&1; then
    zenity --info --title="$title" --text="$message" --width=560 >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "$title" "$message" >/dev/null 2>&1 || true
  fi
}

open_report_location() {
  local path="$1"
  local directory
  directory="$(dirname "$path")"
  if [[ "${TRIVIEW_DIAGNOSTIC_NO_OPEN:-0}" == "1" ]]; then
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    nohup xdg-open "$directory" >/dev/null 2>&1 &
  elif command -v thunar >/dev/null 2>&1; then
    nohup thunar "$directory" >/dev/null 2>&1 &
  fi
}

reason=""
if [[ -z "$CURRENT_TARGET" || ! -d "$CURRENT_TARGET" ]]; then
  reason="Runtime estável ativo ausente"
elif [[ ! -x "$CURRENT_TARGET/scripts/candidate-launch.sh" ]]; then
  reason="Lançador monitorado ausente na release estável"
elif ! command -v flock >/dev/null 2>&1; then
  reason="flock indisponível para verificar instância única"
else
  exec 8>"$APP_LOCK"
  if ! flock -n 8; then
    reason="O TriView já está aberto. Feche a aplicação antes de iniciar o diagnóstico caixa-preta."
  else
    # A verificação é instantânea. O coletor precisa que o lançador monitorado
    # adquira o mesmo lock quando iniciar a aplicação sob observação.
    flock -u 8
  fi
fi

if [[ -z "$reason" ]]; then
  VERSION="$(tr -d '[:space:]' < "$APP_ROOT/VERSION" 2>/dev/null || true)"
  RUNTIME_SHA="$(python3 - "$APP_ROOT/ACTIVE-CANDIDATE.json" <<'PY'
from __future__ import annotations

import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    print("")
else:
    print(payload.get("ref", ""))
PY
)"
  export TRIVIEW_RUNTIME_SHA="$RUNTIME_SHA"
  export TRIVIEW_RUNTIME_VERSION="$VERSION"
  export PYTHONPATH="$CURRENT_TARGET/src${PYTHONPATH:+:$PYTHONPATH}"
  cd "$CURRENT_TARGET"

  set +e
  package="$(python3 -m triview_workspace.diagnostic_blackbox_xtest \
    --output-dir "$REPORT_DIR" \
    --timeout-seconds "${TRIVIEW_DIAGNOSTIC_TIMEOUT_SECONDS:-900}" \
    --auto-launch \
    --auto-stop-on-application-exit 2>>"$APP_STATE/diagnostic-blackbox.stderr.log")"
  status="$?"
  set -e
  package="$(printf '%s\n' "$package" | tail -n 1)"
  if [[ "$status" -eq 0 && -n "$package" && -f "$package" ]]; then
    printf 'Pacote de diagnóstico estável: %s\n' "$package"
    show_result \
      "TriView — diagnóstico concluído" \
      "Pacote sanitizado gerado com sucesso:\n\n$package\n\nEnvie somente este arquivo ZIP para auditoria."
    open_report_location "$package"
    exit 0
  fi
  reason="Falha da sessão caixa-preta estável (status=$status)"
fi

if [[ -n "$CURRENT_TARGET" && -d "$CURRENT_TARGET/src" ]]; then
  export PYTHONPATH="$CURRENT_TARGET/src${PYTHONPATH:+:$PYTHONPATH}"
fi
set +e
fallback_package="$(python3 -m triview_workspace.diagnostic_fallback_shareable \
  --output-dir "$REPORT_DIR" \
  --reason "$reason" 2>>"$APP_STATE/diagnostic-blackbox.stderr.log")"
fallback_status="$?"
set -e
fallback_package="$(printf '%s\n' "$fallback_package" | tail -n 1)"

if [[ "$fallback_status" -eq 0 && -n "$fallback_package" && -f "$fallback_package" ]]; then
  printf 'Pacote de contingência estável: %s\n' "$fallback_package"
  printf 'Motivo da contingência: %s\n' "$reason"
  show_result \
    "TriView — diagnóstico parcial" \
    "A sessão completa não terminou. Foi criado um pacote sanitizado de contingência:\n\n$fallback_package\n\nMotivo: $reason\n\nEle não representa PASS funcional."
  open_report_location "$fallback_package"
  exit 1
fi

printf 'Falha no diagnóstico estável: %s\n' "$reason" >&2
show_result \
  "TriView — falha no diagnóstico" \
  "Não foi possível gerar o pacote completo nem o pacote sanitizado de contingência.\n\nMotivo: $reason"
exit 1
