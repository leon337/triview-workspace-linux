#!/usr/bin/env bash
set -Eeuo pipefail

APP_ROOT="${1:?APP_ROOT ausente}"
DATA_ROOT="${2:?DATA_ROOT ausente}"
STATE_ROOT="${3:?STATE_ROOT ausente}"
MODULE="${4:?MODULE ausente}"
CURRENT="$APP_ROOT/current"
CURRENT_TARGET="$(readlink -f "$CURRENT" 2>/dev/null || true)"

mkdir -p "$STATE_ROOT/triview-workspace"
LAUNCH_LOG="$STATE_ROOT/triview-workspace/launcher.log"
STDOUT_LOG="$STATE_ROOT/triview-workspace/app.stdout.log"
STDERR_LOG="$STATE_ROOT/triview-workspace/app.stderr.log"

if [[ -z "$CURRENT_TARGET" || ! -d "$CURRENT_TARGET" ]]; then
  printf 'ERRO: candidato ativo ausente ou inválido: %s\n' "$CURRENT" | tee -a "$LAUNCH_LOG" >&2
  exit 1
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
} >>"$LAUNCH_LOG"

export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
export PYTHONPATH="$CURRENT_TARGET/src${PYTHONPATH:+:$PYTHONPATH}"
export TRIVIEW_RUNTIME_ROOT="$CURRENT_TARGET"
export TRIVIEW_RUNTIME_SHA="$RESOLVED_SHA"
export TRIVIEW_RUNTIME_MODULE="$MODULE"
cd "$CURRENT_TARGET"

exec python3 -m "$MODULE" >>"$STDOUT_LOG" 2>>"$STDERR_LOG"
