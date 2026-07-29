#!/usr/bin/env bash
set -Eeuo pipefail

REPO="${TRIVIEW_REPO:-leon337/triview-workspace-linux}"
APP_ROOT="${TRIVIEW_APP_ROOT:-$HOME/.local/share/triview-workspace}"
BACKUP_ROOT="${TRIVIEW_BACKUP_ROOT:-$HOME/.local/share/triview-workspace-backups}"
DATA_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}"
STATE_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/triview-workspace"
CATALOG_FILE="${TRIVIEW_DATA_FILE:-$DATA_ROOT/triview-workspace/workspaces.json}"
CURRENT_LINK="$APP_ROOT/current"
VERSION_FILE="$APP_ROOT/VERSION"
CHANNEL_FILE="$APP_ROOT/UPDATE_CHANNEL"
ACTIVE_CANDIDATE_FILE="$APP_ROOT/ACTIVE-CANDIDATE.json"
LOCK_FILE="$STATE_ROOT/lifecycle.lock"
REPORTS_DIR="$STATE_ROOT/stable-rollback-reports"
LOGS_DIR="$STATE_ROOT/stable-rollbacks"
TRANSACTIONS_DIR="$STATE_ROOT/transactions"

BACKUP_OVERRIDE=""
DRY_RUN=0
TMP_DIR=""
RESTORE_DIR=""
COMMITTED=0
RESULT_SUMMARY="Rollback encerrado."
TEMP_VERSION_FILE=""
TEMP_CHANNEL_FILE=""
TEMP_ACTIVE_FILE=""
TRANSACTION_FILE=""

while (($#)); do
  case "$1" in
    --backup)
      (($# >= 2)) || {
        printf 'Uso: stable-rollback.sh [--backup CAMINHO] [--dry-run]\n' >&2
        exit 2
      }
      BACKUP_OVERRIDE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --help|-h)
      printf 'Uso: stable-rollback.sh [--backup CAMINHO] [--dry-run]\n'
      exit 0
      ;;
    *)
      printf 'Opção desconhecida: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

mkdir -p \
  "$APP_ROOT/releases" \
  "$BACKUP_ROOT" \
  "$STATE_ROOT" \
  "$REPORTS_DIR" \
  "$LOGS_DIR" \
  "$TRANSACTIONS_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%S%NZ)"
LOG_FILE="$LOGS_DIR/rollback-$STAMP.log"

log() {
  printf '[TriView Stable Rollback] %s\n' "$*" | tee -a "$LOG_FILE"
}

fail() {
  RESULT_SUMMARY="$*"
  log "ERRO: $*"
  exit 1
}

show_result() {
  local status="$1"
  ((DRY_RUN)) && return 0
  [[ "${TRIVIEW_NONINTERACTIVE:-0}" == "1" ]] && return 0

  local title text icon
  if ((status == 0)); then
    title='TriView Workspace — rollback concluído'
    text="O rollback foi concluído com sucesso.\n\n$RESULT_SUMMARY\n\nLog: $LOG_FILE"
    icon='--info'
  else
    title='TriView Workspace — erro no rollback'
    text="O rollback terminou com erro (código $status).\n\n$RESULT_SUMMARY\n\nLog: $LOG_FILE"
    icon='--error'
  fi

  if command -v zenity >/dev/null 2>&1 \
    && [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    zenity "$icon" --title="$title" --text="$text" --width=560 >/dev/null 2>&1 || true
  fi
  if [[ -t 0 ]]; then
    printf '\nPressione ENTER para fechar.\n'
    read -r _ || true
  fi
}

mark_transaction_incomplete() {
  [[ -n "$TRANSACTION_FILE" && -f "$TRANSACTION_FILE" ]] || return 0
  python3 - "$TRANSACTION_FILE" <<'PY' || true
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, ValueError):
    payload = {"schema_version": 1, "event": "stable_rollback_transaction"}
payload["state"] = "commit_incomplete"
payload["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
temporary = path.with_suffix(".tmp")
temporary.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
temporary.replace(path)
PY
}

cleanup() {
  local status=$?
  trap - EXIT
  [[ -n "$TMP_DIR" ]] && rm -rf "$TMP_DIR"
  [[ -n "$TEMP_VERSION_FILE" ]] && rm -f "$TEMP_VERSION_FILE"
  [[ -n "$TEMP_CHANNEL_FILE" ]] && rm -f "$TEMP_CHANNEL_FILE"
  [[ -n "$TEMP_ACTIVE_FILE" ]] && rm -f "$TEMP_ACTIVE_FILE"
  if ((COMMITTED == 0)) && [[ -n "$RESTORE_DIR" && -d "$RESTORE_DIR" ]]; then
    rm -rf "$RESTORE_DIR"
  elif ((status != 0 && COMMITTED == 1)); then
    mark_transaction_incomplete
    log "AVISO: o código restaurado permanece ativo; a transação registra finalização incompleta."
  fi
  show_result "$status"
  exit "$status"
}
trap cleanup EXIT

for command in python3 flock cp mv readlink; do
  command -v "$command" >/dev/null 2>&1 || fail "$command não encontrado."
done

exec 8>"$LOCK_FILE"
if ! flock -n 8; then
  RESULT_SUMMARY="outra operação de instalação, atualização ou rollback já está em execução."
  log "ERRO: $RESULT_SUMMARY"
  exit 2
fi

[[ -L "$CURRENT_LINK" ]] || fail "instalação ativa não encontrada em $CURRENT_LINK."
CURRENT_TARGET="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
[[ -d "$CURRENT_TARGET" ]] || fail "release ativa inválida: $CURRENT_TARGET"

RUNNING_PIDS="$(python3 - "$APP_ROOT" <<'PY'
from __future__ import annotations

import pathlib
import sys

app_root = pathlib.Path(sys.argv[1]).expanduser().resolve()
for cwd_path in pathlib.Path("/proc").glob("[0-9]*/cwd"):
    try:
        cwd = cwd_path.resolve()
        cwd.relative_to(app_root)
        cmdline = (cwd_path.parent / "cmdline").read_bytes()
    except (OSError, PermissionError, ValueError):
        continue
    if b"triview_workspace" in cmdline:
        print(cwd_path.parent.name)
PY
)"
[[ -z "$RUNNING_PIDS" ]] || fail "feche o TriView Workspace antes do rollback. Instância ativa: $RUNNING_PIDS"

SELECTED_BACKUP="$(python3 - "$BACKUP_ROOT" "$BACKUP_OVERRIDE" <<'PY'
from __future__ import annotations

import pathlib
import sys

root = pathlib.Path(sys.argv[1]).expanduser().resolve()
override = sys.argv[2].strip()
if not root.is_dir():
    raise SystemExit("raiz de backups ausente")

if override:
    candidate = pathlib.Path(override).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise SystemExit("backup fora da raiz controlada") from exc
    candidates = [candidate]
else:
    candidates = sorted(
        (
            path.resolve()
            for path in root.iterdir()
            if path.is_dir() and not path.is_symlink() and (path / "current").is_dir()
        ),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )

for candidate in candidates:
    source = candidate / "current"
    if (
        candidate.is_dir()
        and not candidate.is_symlink()
        and source.is_dir()
        and not source.is_symlink()
        and (source / "pyproject.toml").is_file()
        and (source / "src" / "triview_workspace").is_dir()
    ):
        print(candidate)
        break
else:
    raise SystemExit("nenhum backup restaurável encontrado")
PY
)" || fail "nenhum backup restaurável e controlado foi encontrado."

BACKUP_SOURCE="$SELECTED_BACKUP/current"
[[ -f "$BACKUP_SOURCE/config/workspaces/three-mobile.json" ]] \
  || fail "backup não contém o workspace de diagnóstico."
[[ -f "$BACKUP_SOURCE/src/triview_workspace/cli.py" ]] \
  || fail "backup não contém o módulo principal."

VERSION="$(python3 - "$BACKUP_SOURCE/pyproject.toml" <<'PY'
from __future__ import annotations

import pathlib
import re
import sys

text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
if not match:
    raise SystemExit("versão ausente")
print(match.group(1))
PY
)" || fail "versão do backup inválida."

TMP_DIR="$(mktemp -d)"
mkdir -p "$TMP_DIR/restore"
cp -a "$BACKUP_SOURCE/." "$TMP_DIR/restore/"
python3 -m compileall -q "$TMP_DIR/restore/src" \
  || fail "código do backup não compila."

(
  cd "$TMP_DIR/restore"
  export PYTHONPATH="$TMP_DIR/restore/src"
  python3 -m triview_workspace.cli \
    --diagnostic \
    --workspace "$TMP_DIR/restore/config/workspaces/three-mobile.json" \
    --data-file "$TMP_DIR/diagnostic-workspaces.json" >/dev/null
  python3 - <<'PY'
from triview_workspace import cli

if not callable(getattr(cli, "main", None)):
    raise SystemExit("módulo principal sem main()")
PY
) || fail "diagnóstico isolado do backup falhou."

resolve_stable_tag_sha() {
  local version="$1"
  local ref_url tag_url object_type object_sha
  local -a ref_info tag_info
  command -v curl >/dev/null 2>&1 || return 1

  ref_url="https://api.github.com/repos/$REPO/git/ref/tags/v$version"
  mapfile -t ref_info < <(
    curl -fsSL -H 'Accept: application/vnd.github+json' "$ref_url" \
      | python3 -c '
import json, sys
payload = json.load(sys.stdin)
obj = payload.get("object") or {}
print(obj.get("type", ""))
print(obj.get("sha", ""))
'
  ) || return 1
  ((${#ref_info[@]} == 2)) || return 1
  object_type="${ref_info[0]}"
  object_sha="${ref_info[1]}"

  if [[ "$object_type" == "tag" ]]; then
    tag_url="https://api.github.com/repos/$REPO/git/tags/$object_sha"
    mapfile -t tag_info < <(
      curl -fsSL -H 'Accept: application/vnd.github+json' "$tag_url" \
        | python3 -c '
import json, sys
payload = json.load(sys.stdin)
obj = payload.get("object") or {}
print(obj.get("type", ""))
print(obj.get("sha", ""))
'
    ) || return 1
    ((${#tag_info[@]} == 2)) || return 1
    [[ "${tag_info[0]}" == "commit" ]] || return 1
    object_sha="${tag_info[1]}"
  elif [[ "$object_type" != "commit" ]]; then
    return 1
  fi

  [[ "$object_sha" =~ ^[0-9a-f]{40}$ ]] || return 1
  printf '%s\n' "$object_sha"
}

RESTORED_REF="${TRIVIEW_STABLE_REF:-}"
RESTORED_STATUS="stable-rollback-restored"
if [[ -n "$RESTORED_REF" && ! "$RESTORED_REF" =~ ^[0-9a-f]{40}$ ]]; then
  log "AVISO: SHA estável fornecido é inválido; proveniência ficará pendente."
  RESTORED_REF=""
  RESTORED_STATUS="stable-rollback-ref-unresolved"
elif [[ -z "$RESTORED_REF" ]]; then
  if ! RESTORED_REF="$(resolve_stable_tag_sha "$VERSION")"; then
    log "AVISO: tag v$VERSION não pôde ser resolvida; o rollback continuará com proveniência pendente."
    RESTORED_REF=""
    RESTORED_STATUS="stable-rollback-ref-unresolved"
  fi
fi

log "Backup selecionado: $SELECTED_BACKUP"
log "Versão validada: $VERSION"
log "SHA restaurado: ${RESTORED_REF:-não resolvido}"
log "Dados persistentes serão preservados: $CATALOG_FILE"

if ((DRY_RUN)); then
  RESULT_SUMMARY="Backup $SELECTED_BACKUP validado para restauração da versão $VERSION."
  log "DRY-RUN concluído. Nenhuma alteração foi feita."
  exit 0
fi

PRE_ROLLBACK_BACKUP="$BACKUP_ROOT/rollback-$STAMP"
mkdir -p "$PRE_ROLLBACK_BACKUP"
cp -a "$CURRENT_TARGET" "$PRE_ROLLBACK_BACKUP/current"
if [[ -f "$CATALOG_FILE" ]]; then
  cp -a "$CATALOG_FILE" "$PRE_ROLLBACK_BACKUP/workspaces.json"
fi

python3 - "$PRE_ROLLBACK_BACKUP/backup.json" "$CURRENT_TARGET" "$SELECTED_BACKUP" "$CATALOG_FILE" <<'PY'
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

path, current_target, selected_backup, catalog = sys.argv[1:]
payload = {
    "schema_version": 1,
    "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "reason": "pre-stable-rollback",
    "current_target": current_target,
    "selected_backup": selected_backup,
    "catalog_path": catalog,
    "data_restored": False,
}
pathlib.Path(path).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

safe_version="$(printf '%s' "$VERSION" | tr -cd 'A-Za-z0-9._-')"
[[ -n "$safe_version" ]] || fail "versão não pode formar diretório seguro."
RESTORE_DIR="$APP_ROOT/releases/$safe_version-stable-rollback-$STAMP"
mkdir -p "$RESTORE_DIR"
cp -a "$TMP_DIR/restore/." "$RESTORE_DIR/"
touch "$RESTORE_DIR/.installed"

python3 - \
  "$RESTORE_DIR/stable-release.json" \
  "$RESTORE_DIR/candidate-release.json" \
  "$VERSION" \
  "$RESTORED_REF" \
  "$RESTORED_STATUS" \
  "$SELECTED_BACKUP" \
  "$PRE_ROLLBACK_BACKUP" <<'PY'
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

stable_path = pathlib.Path(sys.argv[1])
candidate_path = pathlib.Path(sys.argv[2])
version, ref, status, selected_backup, pre_backup = sys.argv[3:]
stable_payload = {
    "schema_version": 1,
    "event": "stable_rollback_restored",
    "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "version": version,
    "resolved_sha": ref,
    "status": status,
    "selected_backup": selected_backup,
    "pre_rollback_backup": pre_backup,
}
stable_path.write_text(
    json.dumps(stable_payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
candidate_payload = {
    "schema_version": 1,
    "candidate_id": "stable-rollback",
    "version": version,
    "resolved_sha": ref,
    "source_ref": f"v{version}",
    "module": "triview_workspace.cli",
    "status": status,
}
candidate_path.write_text(
    json.dumps(candidate_payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

TEMP_VERSION_FILE="$APP_ROOT/.VERSION-$STAMP"
TEMP_CHANNEL_FILE="$APP_ROOT/.UPDATE_CHANNEL-$STAMP"
TEMP_ACTIVE_FILE="$APP_ROOT/.ACTIVE-CANDIDATE-$STAMP.json"
printf '%s\n' "$VERSION" > "$TEMP_VERSION_FILE"
printf 'stable\n' > "$TEMP_CHANNEL_FILE"
python3 - \
  "$TEMP_ACTIVE_FILE" \
  "$VERSION" \
  "$RESTORED_REF" \
  "$RESTORED_STATUS" \
  "$SELECTED_BACKUP" <<'PY'
from __future__ import annotations

import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
version, ref, status, selected_backup = sys.argv[2:]
payload = {
    "schema_version": 1,
    "channel": "stable",
    "candidate_id": "stable-rollback",
    "version": version,
    "ref": ref,
    "module": "triview_workspace.cli",
    "status": status,
    "selected_backup": selected_backup,
}
path.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

TRANSACTION_FILE="$TRANSACTIONS_DIR/$STAMP-stable-rollback.json"
python3 - \
  "$TRANSACTION_FILE" \
  "$CURRENT_TARGET" \
  "$RESTORE_DIR" \
  "$SELECTED_BACKUP" \
  "$PRE_ROLLBACK_BACKUP" \
  "$VERSION" \
  "$RESTORED_REF" \
  "$RESTORED_STATUS" <<'PY'
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

(
    path,
    old_current,
    new_current,
    selected_backup,
    pre_backup,
    version,
    ref,
    status,
) = sys.argv[1:]
payload = {
    "schema_version": 1,
    "event": "stable_rollback_transaction",
    "state": "prepared",
    "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "old_current": old_current,
    "new_current": new_current,
    "selected_backup": selected_backup,
    "pre_rollback_backup": pre_backup,
    "version": version,
    "ref": ref,
    "provenance_status": status,
}
pathlib.Path(path).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

TEMP_LINK="$APP_ROOT/.current-rollback-$STAMP"
ln -s "$RESTORE_DIR" "$TEMP_LINK"
mv -Tf "$TEMP_LINK" "$CURRENT_LINK"
COMMITTED=1

mv -f "$TEMP_VERSION_FILE" "$VERSION_FILE"
TEMP_VERSION_FILE=""
mv -f "$TEMP_CHANNEL_FILE" "$CHANNEL_FILE"
TEMP_CHANNEL_FILE=""
mv -f "$TEMP_ACTIVE_FILE" "$ACTIVE_CANDIDATE_FILE"
TEMP_ACTIVE_FILE=""

python3 - "$TRANSACTION_FILE" <<'PY'
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload["state"] = "committed"
payload["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
temporary = path.with_suffix(".tmp")
temporary.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
temporary.replace(path)
PY

REPORT="$REPORTS_DIR/$STAMP-rollback.json"
python3 - \
  "$REPORT" \
  "$CURRENT_TARGET" \
  "$RESTORE_DIR" \
  "$SELECTED_BACKUP" \
  "$PRE_ROLLBACK_BACKUP" \
  "$CATALOG_FILE" \
  "$LOG_FILE" \
  "$VERSION" \
  "$RESTORED_REF" \
  "$RESTORED_STATUS" \
  "$TRANSACTION_FILE" \
  "$ACTIVE_CANDIDATE_FILE" <<'PY'
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

(
    path,
    old_current,
    new_current,
    selected_backup,
    pre_backup,
    catalog,
    log_path,
    version,
    ref,
    status,
    transaction,
    active_candidate,
) = sys.argv[1:]
payload = {
    "schema_version": 1,
    "event": "stable_rollback_committed",
    "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "old_current": old_current,
    "new_current": new_current,
    "selected_backup": selected_backup,
    "pre_rollback_backup": pre_backup,
    "catalog_path": catalog,
    "version": version,
    "ref": ref,
    "provenance_status": status,
    "data_restored": False,
    "data_policy": "preserve-current-user-data",
    "atomic_current_switch": True,
    "transaction": transaction,
    "active_candidate": active_candidate,
    "log": log_path,
}
pathlib.Path(path).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

RESTORE_DIR=""
RESULT_SUMMARY="Versão restaurada: $VERSION. Dados preservados. Relatório: $REPORT"
log "Rollback concluído."
log "Versão ativa: $VERSION"
log "SHA ativo: ${RESTORED_REF:-não resolvido}"
log "Dados preservados: $CATALOG_FILE"
log "Backup pré-rollback: $PRE_ROLLBACK_BACKUP"
log "Transação: $TRANSACTION_FILE"
log "Relatório: $REPORT"
