#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${1:?APP_ROOT ausente}"
DATA_ROOT="${2:?DATA_ROOT ausente}"
STATE_ROOT="${3:?STATE_ROOT ausente}"
MODULE="${4:?MODULE ausente}"
CURRENT="$APP_ROOT/current"
CURRENT_TARGET="$(readlink -f "$CURRENT" 2>/dev/null || true)"

APP_STATE="$STATE_ROOT/triview-workspace"
mkdir -p "$APP_STATE"
LAUNCH_LOG="$APP_STATE/launcher.log"
STDOUT_LOG="$APP_STATE/app.stdout.log"
STDERR_LOG="$APP_STATE/app.stderr.log"
LOCK_FILE="$APP_STATE/app.lock"
PID_FILE="$APP_STATE/app.pid"

if [[ -z "$CURRENT_TARGET" || ! -d "$CURRENT_TARGET" ]]; then
  printf 'ERRO: candidato ativo ausente ou inválido: %s\n' "$CURRENT" | tee -a "$LAUNCH_LOG" >&2
  exit 1
fi

install_x11_dependencies() {
  local missing=()
  command -v Xephyr >/dev/null 2>&1 || missing+=(xserver-xephyr)
  command -v xauth >/dev/null 2>&1 || missing+=(xauth)
  command -v xdotool >/dev/null 2>&1 || missing+=(xdotool)
  command -v xwininfo >/dev/null 2>&1 || missing+=(x11-utils)
  command -v xrandr >/dev/null 2>&1 || missing+=(x11-xserver-utils)
  if [[ "${#missing[@]}" -eq 0 ]]; then
    return 0
  fi
  if [[ "${TRIVIEW_DISABLE_SYSTEM_PACKAGE_INSTALL:-0}" == "1" ]]; then
    printf 'ERRO: dependências X11 ausentes: %s\n' "${missing[*]}" | tee -a "$LAUNCH_LOG" >&2
    return 1
  fi
  command -v apt-get >/dev/null 2>&1 || {
    printf 'ERRO: dependências X11 ausentes e apt-get indisponível: %s\n' \
      "${missing[*]}" | tee -a "$LAUNCH_LOG" >&2
    return 1
  }
  {
    printf 'installing_x11_dependencies=%s\n' "${missing[*]}"
  } >>"$LAUNCH_LOG"
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    apt-get update
    apt-get install -y --no-install-recommends "${missing[@]}"
  elif command -v pkexec >/dev/null 2>&1; then
    pkexec apt-get update
    pkexec apt-get install -y --no-install-recommends "${missing[@]}"
  elif command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends "${missing[@]}"
  else
    printf 'ERRO: não há pkexec ou sudo para instalar: %s\n' \
      "${missing[*]}" | tee -a "$LAUNCH_LOG" >&2
    return 1
  fi
  for required in Xephyr xauth xdotool xwininfo xrandr; do
    command -v "$required" >/dev/null 2>&1 || {
      printf 'ERRO: dependência continuou ausente após a instalação: %s\n' \
        "$required" | tee -a "$LAUNCH_LOG" >&2
      return 1
    }
  done
}

install_x11_dependencies

if ! command -v flock >/dev/null 2>&1; then
  printf 'ERRO: flock não está disponível para garantir instância única.\n' \
    | tee -a "$LAUNCH_LOG" >&2
  exit 1
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  {
    printf '\n=== TriView duplicate launch %s ===\n' "$(date --iso-8601=seconds)"
    printf 'current_target=%s\n' "$CURRENT_TARGET"
    printf 'module=%s\n' "$MODULE"
    printf 'result=existing_instance_activated\n'
  } >>"$LAUNCH_LOG"

  if command -v xdotool >/dev/null 2>&1; then
    EXISTING_WINDOW="$(
      xdotool search --onlyvisible --name '^TriView Workspace$' 2>/dev/null \
        | tail -n 1 || true
    )"
    if [[ -n "$EXISTING_WINDOW" ]]; then
      xdotool windowactivate --sync "$EXISTING_WINDOW" 2>/dev/null || true
    fi
  fi
  exit 0
fi

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

{
  printf '\n=== TriView launch %s ===\n' "$(date --iso-8601=seconds)"
  printf 'launcher=%s\n' "$0"
  printf 'current_link=%s\n' "$CURRENT"
  printf 'current_target=%s\n' "$CURRENT_TARGET"
  printf 'metadata=%s\n' "$METADATA"
  printf 'resolved_sha=%s\n' "$RESOLVED_SHA"
  printf 'module=%s\n' "$MODULE"
  printf 'python=%s\n' "$(command -v python3)"
  printf 'display=%s\n' "${DISPLAY:-}"
  printf 'session_type=%s\n' "${XDG_SESSION_TYPE:-}"
  printf 'lock_file=%s\n' "$LOCK_FILE"
  printf 'xephyr=%s\n' "$(command -v Xephyr)"
  printf 'xauth=%s\n' "$(command -v xauth)"
} >>"$LAUNCH_LOG"

export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
export PYTHONPATH="$CURRENT_TARGET/src${PYTHONPATH:+:$PYTHONPATH}"
export TRIVIEW_RUNTIME_ROOT="$CURRENT_TARGET"
export TRIVIEW_RUNTIME_SHA="$RESOLVED_SHA"
export TRIVIEW_RUNTIME_MODULE="$MODULE"
cd "$CURRENT_TARGET"

APP_PID=""
cleanup() {
  rm -f "$PID_FILE"
}
forward_signal() {
  if [[ -n "$APP_PID" ]]; then
    kill -TERM "$APP_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap forward_signal HUP INT TERM

python3 -m "$MODULE" >>"$STDOUT_LOG" 2>>"$STDERR_LOG" &
APP_PID="$!"
printf '%s\n' "$APP_PID" >"$PID_FILE"
printf 'app_pid=%s\n' "$APP_PID" >>"$LAUNCH_LOG"

set +e
wait "$APP_PID"
status="$?"
set -e
printf 'exit_status=%s\n' "$status" >>"$LAUNCH_LOG"
exit "$status"
