#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE_ID="${1:?CANDIDATE_ID ausente}"
APP_ROOT="${2:?APP_ROOT ausente}"
DATA_ROOT="${3:?DATA_ROOT ausente}"
STATE_ROOT="${4:?STATE_ROOT ausente}"
MODULE="${5:?MODULE ausente}"
APP_STATE="$STATE_ROOT/triview-workspace"
BACKUPS_DIR="$APP_STATE/backups"
ROLLBACK_REPORTS_DIR="$APP_STATE/rollback-reports"
LOGS_DIR="$APP_STATE/rollbacks"
LIFECYCLE_LOCK="$APP_STATE/lifecycle.lock"

mkdir -p "$APP_STATE" "$BACKUPS_DIR" "$ROLLBACK_REPORTS_DIR" "$LOGS_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOGS_DIR/rollback-$STAMP.log"

log() { printf '[TriView Rollback %s] %s\n' "$CANDIDATE_ID" "$*" | tee -a "$LOG"; }
fail() { log "ERRO: $*"; exit 1; }

for command in python3 tar sha256sum flock; do
  command -v "$command" >/dev/null 2>&1 || fail "$command não encontrado."
done

exec 8>"$LIFECYCLE_LOCK"
if ! flock -n 8; then
  log "ERRO: outra operação de instalação, atualização ou rollback já está em execução."
  exit 2
fi

RUNNING_PIDS="$(python3 - "$APP_ROOT" "$MODULE" <<'PY'
from __future__ import annotations

import pathlib
import sys

app_root = pathlib.Path(sys.argv[1]).expanduser().resolve()
expected_module = sys.argv[2]
releases = app_root / "releases"
for environ_path in pathlib.Path("/proc").glob("[0-9]*/environ"):
    try:
        raw = environ_path.read_bytes()
    except (OSError, PermissionError):
        continue
    entries = {}
    for item in raw.split(b"\0"):
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        entries[key.decode(errors="replace")] = value.decode(errors="replace")
    if entries.get("TRIVIEW_RUNTIME_MODULE") != expected_module:
        continue
    runtime_root = entries.get("TRIVIEW_RUNTIME_ROOT")
    if not runtime_root:
        continue
    try:
        pathlib.Path(runtime_root).expanduser().resolve().relative_to(releases)
    except (OSError, ValueError):
        continue
    print(environ_path.parent.name)
PY
)"

if [[ -n "$RUNNING_PIDS" ]]; then
  fail "feche o TriView Workspace antes do rollback. Instância ativa: $RUNNING_PIDS"
fi

current_link="$APP_ROOT/current"
previous_link="$APP_ROOT/previous"
[[ -L "$current_link" ]] || fail "link current ausente."
[[ -L "$previous_link" ]] || fail "link previous ausente."

current_target="$(readlink -f "$current_link" 2>/dev/null || true)"
previous_target="$(readlink -f "$previous_link" 2>/dev/null || true)"
[[ -d "$current_target" ]] || fail "release atual inválido: $current_target"
[[ -d "$previous_target" ]] || fail "release anterior inválido: $previous_target"
[[ "$current_target" == "$APP_ROOT/releases/"* ]] || fail "release atual fora da raiz controlada."
[[ "$previous_target" == "$APP_ROOT/releases/"* ]] || fail "release anterior fora da raiz controlada."
[[ "$current_target" != "$previous_target" ]] || fail "current e previous apontam para o mesmo release."

release_sha() {
  python3 - "$1/candidate-release.json" <<'PY'
import json
import pathlib
import re
import sys
path = pathlib.Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
sha = str(payload.get("resolved_sha", "")).lower()
if not re.fullmatch(r"[0-9a-f]{40}", sha):
    raise SystemExit("resolved_sha inválido")
print(sha)
PY
}

current_sha="$(release_sha "$current_target")"
previous_sha="$(release_sha "$previous_target")"

backup_dir="$BACKUPS_DIR/${STAMP}-${current_sha:0:12}-pre-rollback"
mkdir -p "$backup_dir"
tar -C "$DATA_ROOT" -czf "$backup_dir/data.tar.gz" .
tar \
  --exclude='./triview-workspace/backups' \
  --exclude='./triview-workspace/transactions' \
  -C "$STATE_ROOT" -czf "$backup_dir/state.tar.gz" .
(
  cd "$backup_dir"
  sha256sum data.tar.gz state.tar.gz > SHA256SUMS
  sha256sum -c SHA256SUMS >/dev/null
)

python3 - "$backup_dir/backup.json" "$current_target" "$previous_target" \
  "$current_sha" "$previous_sha" "$backup_dir" <<'PY'
import datetime as dt
import json
import pathlib
import sys
path, current_target, previous_target, current_sha, previous_sha, backup_dir = sys.argv[1:]
root = pathlib.Path(backup_dir)
checksums = {}
for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    digest, name = line.split(maxsplit=1)
    checksums[name.strip()] = digest
payload = {
    "schema_version": 1,
    "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "reason": "pre-rollback",
    "current_target": current_target,
    "previous_target": previous_target,
    "current_sha": current_sha,
    "previous_sha": previous_sha,
    "checksums": checksums,
    "verified": True,
    "restore_policy": "manual-explicit-only",
}
pathlib.Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

log "Backup verificável criado: $backup_dir"
log "Rollback de código: $current_sha -> $previous_sha"
log "Dados não serão restaurados nem removidos."

python3 - "$current_link" "$previous_link" <<'PY'
from __future__ import annotations

import ctypes
import os
import sys

AT_FDCWD = -100
RENAME_EXCHANGE = 2
current, previous = (os.fsencode(value) for value in sys.argv[1:])
libc = ctypes.CDLL(None, use_errno=True)
renameat2 = getattr(libc, "renameat2", None)
if renameat2 is None:
    raise SystemExit("renameat2 indisponível; rollback atômico recusado.")
renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
renameat2.restype = ctypes.c_int
result = renameat2(AT_FDCWD, current, AT_FDCWD, previous, RENAME_EXCHANGE)
if result != 0:
    error = ctypes.get_errno()
    raise OSError(error, os.strerror(error))
PY

new_current="$(readlink -f "$current_link" 2>/dev/null || true)"
new_previous="$(readlink -f "$previous_link" 2>/dev/null || true)"
[[ "$new_current" == "$previous_target" ]] || fail "current não aponta para o release anterior após a troca."
[[ "$new_previous" == "$current_target" ]] || fail "previous não aponta para o release substituído após a troca."
[[ -f "$new_current/.installed" ]] || fail "release restaurado não está marcado como instalado."

report="$ROLLBACK_REPORTS_DIR/$STAMP-rollback.json"
python3 - "$report" "$current_target" "$previous_target" "$new_current" "$new_previous" \
  "$current_sha" "$previous_sha" "$backup_dir" "$LOG" "$LIFECYCLE_LOCK" <<'PY'
import datetime as dt
import json
import pathlib
import sys
(
    path, old_current, old_previous, new_current, new_previous, old_sha,
    restored_sha, backup_dir, log_path, lifecycle_lock,
) = sys.argv[1:]
payload = {
    "schema_version": 2,
    "event": "rollback_committed",
    "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "old_current": old_current,
    "old_previous": old_previous,
    "new_current": new_current,
    "new_previous": new_previous,
    "old_sha": old_sha,
    "restored_sha": restored_sha,
    "backup_dir": backup_dir,
    "log": log_path,
    "lifecycle_lock": lifecycle_lock,
    "data_restored": False,
    "data_policy": "preserve-later-data",
    "atomic_exchange": True,
}
pathlib.Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

log "Rollback concluído."
log "Release ativo: $new_current"
log "SHA ativo: $previous_sha"
log "Release preservado em previous: $new_previous"
log "Relatório: $report"

if [[ "${TRIVIEW_NONINTERACTIVE:-0}" != "1" ]] && command -v zenity >/dev/null 2>&1; then
  zenity --info --title='Rollback do TriView concluído' \
    --text="Código restaurado para ${previous_sha:0:12}.\n\nDados foram preservados.\nBackup: $backup_dir\nRelatório: $report" \
    || true
fi

if [[ "${TRIVIEW_NONINTERACTIVE:-0}" != "1" ]]; then
  printf '\nPressione ENTER para fechar.\n'
  read -r _ || true
fi
