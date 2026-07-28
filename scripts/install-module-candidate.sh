#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE_ID="${1:?Informe o identificador, por exemplo RC4-1.0.0A1}"
SOURCE_REF="${2:?Informe uma branch, tag ou SHA completo}"
MODULE="${3:?Informe o módulo gráfico, por exemplo triview_workspace.gui}"
UPDATE_REF="${4:-${TRIVIEW_CANDIDATE_UPDATE_REF:-$SOURCE_REF}}"
REPO="${TRIVIEW_REPO:-leon337/triview-workspace-linux}"
SAFE_ID="$(printf '%s' "$CANDIDATE_ID" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9._-')"
[[ -n "$SAFE_ID" ]] || { printf 'Identificador inválido.\n' >&2; exit 2; }
[[ "$REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || {
  printf 'Repositório inválido: %s\n' "$REPO" >&2
  exit 2
}
[[ "$MODULE" =~ ^[A-Za-z_][A-Za-z0-9_.]*$ ]] || {
  printf 'Módulo Python inválido: %s\n' "$MODULE" >&2
  exit 2
}

APP_ROOT="${TRIVIEW_CANDIDATE_ROOT:-$HOME/.local/share/triview-workspace-candidates/$SAFE_ID}"
DATA_ROOT="${TRIVIEW_CANDIDATE_DATA_ROOT:-$HOME/.local/share/triview-workspace-candidate-data/$SAFE_ID}"
STATE_ROOT="${TRIVIEW_CANDIDATE_STATE_ROOT:-$HOME/.local/state/triview-workspace-candidates/$SAFE_ID}"
APP_STATE="$STATE_ROOT/triview-workspace"
BACKUPS_DIR="$APP_STATE/backups"
SWITCH_REPORTS_DIR="$APP_STATE/switch-reports"
TRANSACTIONS_DIR="$APP_STATE/transactions"
BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="$HOME/.local/share/applications"
timestamp="$(date +%Y%m%d-%H%M%S)"
tmp_dir="$(mktemp -d)"
release_dir=""
transaction_file=""
activated=0

cleanup() {
  local status=$?
  rm -rf "$tmp_dir"
  if [[ "$activated" -eq 0 && -n "$release_dir" && -d "$release_dir" ]]; then
    rm -rf "$release_dir"
  fi
  if [[ "$activated" -eq 0 && -n "$transaction_file" ]]; then
    rm -f "$transaction_file"
  fi
  exit "$status"
}
trap cleanup EXIT

log() { printf '[TriView Candidate %s] %s\n' "$CANDIDATE_ID" "$*"; }
fail() { log "ERRO: $*" >&2; exit 1; }

for command in curl tar python3 sha256sum; do
  command -v "$command" >/dev/null 2>&1 || fail "$command não encontrado."
done

resolve_source_ref() {
  if [[ "$SOURCE_REF" =~ ^[0-9a-fA-F]{40}$ ]]; then
    printf '%s' "${SOURCE_REF,,}"
    return 0
  fi

  local encoded_ref api_url response_file
  encoded_ref="$(python3 - "$SOURCE_REF" <<'PY'
import sys
from urllib.parse import quote

print(quote(sys.argv[1], safe=""))
PY
)"
  api_url="https://api.github.com/repos/$REPO/commits/$encoded_ref"
  response_file="$tmp_dir/source-ref.json"
  log "Resolvendo referência mutável '$SOURCE_REF' para um commit imutável..." >&2
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    curl -fsSL \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      "$api_url" -o "$response_file"
  else
    curl -fsSL -H "Accept: application/vnd.github+json" "$api_url" -o "$response_file"
  fi
  python3 - "$response_file" <<'PY'
import json
import re
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
sha = str(payload.get("sha", "")).lower()
if not re.fullmatch(r"[0-9a-f]{40}", sha):
    raise SystemExit("A API do GitHub não retornou um SHA válido.")
print(sha)
PY
}

release_sha() {
  local target="$1"
  python3 - "$target/candidate-release.json" <<'PY'
import json
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(1)
payload = json.loads(path.read_text(encoding="utf-8"))
sha = str(payload.get("resolved_sha", "")).lower()
if not re.fullmatch(r"[0-9a-f]{40}", sha):
    raise SystemExit(1)
print(sha)
PY
}

create_verified_backup() {
  local reason="$1"
  local current_target="$2"
  local previous_target=""
  local current_sha="unknown"
  local backup_stamp backup_dir

  if [[ -L "$APP_ROOT/previous" ]]; then
    previous_target="$(readlink -f "$APP_ROOT/previous" 2>/dev/null || true)"
  fi
  current_sha="$(release_sha "$current_target" 2>/dev/null || printf 'unknown')"
  backup_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_dir="$BACKUPS_DIR/${backup_stamp}-${current_sha:0:12}-${reason}"
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

  python3 - \
    "$backup_dir/backup.json" \
    "$reason" \
    "$current_target" \
    "$previous_target" \
    "$current_sha" \
    "$backup_dir" <<'PY'
import datetime as dt
import json
import pathlib
import sys

path, reason, current_target, previous_target, current_sha, backup_dir = sys.argv[1:]
root = pathlib.Path(backup_dir)
checksums = {}
for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
    digest, name = line.split(maxsplit=1)
    checksums[name.strip()] = digest
payload = {
    "schema_version": 1,
    "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "reason": reason,
    "current_target": current_target,
    "previous_target": previous_target or None,
    "current_sha": current_sha,
    "data_archive": str(root / "data.tar.gz"),
    "state_archive": str(root / "state.tar.gz"),
    "checksums": checksums,
    "verified": True,
    "restore_policy": "manual-explicit-only",
}
pathlib.Path(path).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

  printf '%s\n' "$backup_dir"
}

RESOLVED_SHA="$(resolve_source_ref)" || fail "Não foi possível resolver '$SOURCE_REF'."
[[ "$RESOLVED_SHA" =~ ^[0-9a-f]{40}$ ]] || fail "SHA resolvido inválido."
log "Fonte fixada em $RESOLVED_SHA"

mkdir -p \
  "$APP_ROOT/releases" \
  "$DATA_ROOT" \
  "$STATE_ROOT" \
  "$BACKUPS_DIR" \
  "$SWITCH_REPORTS_DIR" \
  "$TRANSACTIONS_DIR" \
  "$BIN_DIR" \
  "$APPLICATIONS_DIR"

current_link="$APP_ROOT/current"
previous_link="$APP_ROOT/previous"
current_target="$(readlink -f "$current_link" 2>/dev/null || true)"
current_sha=""
if [[ -n "$current_target" && -d "$current_target" ]]; then
  current_sha="$(release_sha "$current_target" 2>/dev/null || true)"
fi

if [[ "$current_sha" == "$RESOLVED_SHA" ]]; then
  report="$SWITCH_REPORTS_DIR/$(date -u +%Y%m%dT%H%M%SZ)-idempotent-noop.json"
  python3 - "$report" "$RESOLVED_SHA" "$current_target" <<'PY'
import datetime as dt
import json
import pathlib
import sys

path, sha, target = sys.argv[1:]
payload = {
    "schema_version": 1,
    "event": "idempotent_update_noop",
    "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "resolved_sha": sha,
    "current_target": target,
    "changed": False,
}
pathlib.Path(path).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
  log "O commit $RESOLVED_SHA já está ativo. Atualização idempotente concluída sem criar release duplicado."
  log "Relatório: $report"
  activated=1
  exit 0
fi

archive_url="https://github.com/$REPO/archive/$RESOLVED_SHA.tar.gz"
log "Baixando snapshot imutável $RESOLVED_SHA..."
curl -fL "$archive_url" -o "$tmp_dir/source.tar.gz"

python3 - "$tmp_dir/source.tar.gz" <<'PY'
import sys
import tarfile
from pathlib import PurePosixPath

with tarfile.open(sys.argv[1], "r:gz") as archive:
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"Entrada insegura no pacote: {member.name}")
PY

mkdir -p "$tmp_dir/extracted"
tar -xzf "$tmp_dir/source.tar.gz" -C "$tmp_dir/extracted" --strip-components=1
[[ -f "$tmp_dir/extracted/pyproject.toml" ]] || fail "Pacote inválido: pyproject.toml ausente."
for required_script in \
  candidate-launch.sh \
  candidate-update.sh \
  candidate-diagnose.sh \
  candidate-rollback.sh; do
  [[ -f "$tmp_dir/extracted/scripts/$required_script" ]] \
    || fail "Script obrigatório ausente: $required_script"
done
python3 -m compileall -q "$tmp_dir/extracted/src"
for script in \
  "$tmp_dir/extracted/scripts/install-module-candidate.sh" \
  "$tmp_dir/extracted/scripts/candidate-launch.sh" \
  "$tmp_dir/extracted/scripts/candidate-update.sh" \
  "$tmp_dir/extracted/scripts/candidate-diagnose.sh" \
  "$tmp_dir/extracted/scripts/candidate-rollback.sh"; do
  bash -n "$script"
done

release_dir="$(mktemp -d "$APP_ROOT/releases/${timestamp}-${RESOLVED_SHA:0:12}-XXXXXX")"
cp -a "$tmp_dir/extracted/." "$release_dir/"
export PYTHONPATH="$release_dir/src"
export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
export TRIVIEW_RUNTIME_ROOT="$release_dir"
export TRIVIEW_RUNTIME_SHA="$RESOLVED_SHA"
export TRIVIEW_RUNTIME_MODULE="$MODULE"
cd "$release_dir"
python3 -m triview_workspace.cli --diagnostic \
  --workspace "$release_dir/config/workspaces/three-mobile.json" \
  --data-file "$DATA_ROOT/diagnostic-workspaces.json" >/dev/null
python3 -c "import importlib; module=importlib.import_module('$MODULE'); assert callable(module.main)"
python3 -c "import triview_workspace.runtime_observability as module; assert callable(module.write_diagnostic_report)"

python3 - "$release_dir/candidate-release.json" "$CANDIDATE_ID" "$REPO" "$SOURCE_REF" "$UPDATE_REF" "$RESOLVED_SHA" "$MODULE" <<'PY'
import datetime as dt
import json
import sys

path, candidate_id, repository, source_ref, update_ref, resolved_sha, module = sys.argv[1:]
payload = {
    "schema_version": 3,
    "candidate_id": candidate_id,
    "repository": repository,
    "source_ref": source_ref,
    "update_ref": update_ref,
    "resolved_sha": resolved_sha,
    "module": module,
    "installed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
PY

touch "$release_dir/.prepared"
backup_dir=""
if [[ -n "$current_target" && -d "$current_target" && "$current_target" == "$APP_ROOT/releases/"* ]]; then
  backup_dir="$(create_verified_backup update "$current_target")"
fi

transaction_file="$TRANSACTIONS_DIR/update-${timestamp}-${RESOLVED_SHA:0:12}.json"
python3 - \
  "$transaction_file" \
  "$current_target" \
  "$release_dir" \
  "$RESOLVED_SHA" \
  "$backup_dir" <<'PY'
import datetime as dt
import json
import pathlib
import sys

path, from_target, to_target, to_sha, backup_dir = sys.argv[1:]
payload = {
    "schema_version": 1,
    "event": "update_prepared",
    "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "from_target": from_target or None,
    "to_target": to_target,
    "to_sha": to_sha,
    "backup_dir": backup_dir or None,
}
pathlib.Path(path).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

if [[ "${TRIVIEW_TEST_FAIL_BEFORE_SWITCH:-0}" == "1" ]]; then
  fail "Interrupção controlada antes da troca atômica."
fi

if [[ -n "$current_target" && -d "$current_target" && "$current_target" == "$APP_ROOT/releases/"* ]]; then
  previous_temp="$APP_ROOT/.previous-$timestamp"
  ln -s "$current_target" "$previous_temp"
  mv -Tf "$previous_temp" "$previous_link"
fi
current_temp="$APP_ROOT/.current-$timestamp"
ln -s "$release_dir" "$current_temp"
mv -Tf "$current_temp" "$current_link"
touch "$release_dir/.installed"
rm -f "$release_dir/.prepared"
activated=1

launcher="$BIN_DIR/triview-workspace-$SAFE_ID"
updater="$BIN_DIR/triview-workspace-$SAFE_ID-update"
diagnostic="$BIN_DIR/triview-workspace-$SAFE_ID-diagnose"
rollback="$BIN_DIR/triview-workspace-$SAFE_ID-rollback"

cat > "$launcher" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec bash "$current_link/scripts/candidate-launch.sh" \
  "$APP_ROOT" \
  "$DATA_ROOT" \
  "$STATE_ROOT" \
  "$MODULE"
EOF

cat > "$updater" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec bash "$current_link/scripts/candidate-update.sh" \
  "$CANDIDATE_ID" \
  "$APP_ROOT" \
  "$DATA_ROOT" \
  "$STATE_ROOT" \
  "$MODULE" \
  "$UPDATE_REF" \
  "$REPO"
EOF

cat > "$diagnostic" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec bash "$current_link/scripts/candidate-diagnose.sh" \
  "$APP_ROOT" \
  "$DATA_ROOT" \
  "$STATE_ROOT" \
  "$MODULE"
EOF

cat > "$rollback" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
exec bash "$current_link/scripts/candidate-rollback.sh" \
  "$CANDIDATE_ID" \
  "$APP_ROOT" \
  "$DATA_ROOT" \
  "$STATE_ROOT" \
  "$MODULE"
EOF
chmod +x "$launcher" "$updater" "$diagnostic" "$rollback"

main_desktop="$APPLICATIONS_DIR/triview-workspace-$SAFE_ID.desktop"
update_desktop="$APPLICATIONS_DIR/triview-workspace-$SAFE_ID-update.desktop"
diagnostic_desktop="$APPLICATIONS_DIR/triview-workspace-$SAFE_ID-diagnose.desktop"
rollback_desktop="$APPLICATIONS_DIR/triview-workspace-$SAFE_ID-rollback.desktop"

cat > "$main_desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TriView Workspace — $CANDIDATE_ID
Comment=Candidato isolado e fixado no commit ${RESOLVED_SHA:0:12}
Exec=$launcher
Icon=preferences-desktop-display
Terminal=false
Categories=Utility;Development;
StartupNotify=true
EOF

cat > "$update_desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Atualizar TriView Workspace — $CANDIDATE_ID
Comment=Atualização idempotente com backup verificável e log persistente
Exec=$updater
Icon=system-software-update
Terminal=true
Categories=Utility;Development;
StartupNotify=true
EOF

cat > "$diagnostic_desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Diagnosticar TriView Workspace — $CANDIDATE_ID
Comment=Coleta proveniência, processos, X11, backups e logs do candidato ativo
Exec=$diagnostic
Icon=utilities-system-monitor
Terminal=false
Categories=Utility;Development;
StartupNotify=true
EOF

cat > "$rollback_desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Reverter TriView Workspace — $CANDIDATE_ID
Comment=Rollback atômico de código sem restaurar dados silenciosamente
Exec=$rollback
Icon=edit-undo
Terminal=true
Categories=Utility;Development;
StartupNotify=true
EOF

chmod +x "$main_desktop" "$update_desktop" "$diagnostic_desktop" "$rollback_desktop"
shortcut_report="$(python3 -m triview_workspace.shortcut_reconciliation \
  --state-root "$STATE_ROOT" \
  --applications-dir "$APPLICATIONS_DIR" \
  --current-launcher "$launcher" \
  --current-launcher "$updater" \
  --current-launcher "$diagnostic" \
  --current-launcher "$rollback")"
update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true

switch_report="$SWITCH_REPORTS_DIR/$(date -u +%Y%m%dT%H%M%SZ)-update.json"
python3 - \
  "$switch_report" \
  "$current_target" \
  "$release_dir" \
  "$RESOLVED_SHA" \
  "$backup_dir" \
  "$shortcut_report" <<'PY'
import datetime as dt
import json
import pathlib
import sys

path, from_target, to_target, to_sha, backup_dir, shortcut_report = sys.argv[1:]
payload = {
    "schema_version": 1,
    "event": "update_committed",
    "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "from_target": from_target or None,
    "to_target": to_target,
    "to_sha": to_sha,
    "backup_dir": backup_dir or None,
    "shortcut_report": shortcut_report,
    "current_valid": pathlib.Path(to_target).is_dir(),
}
pathlib.Path(path).write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
rm -f "$transaction_file"
transaction_file=""

log "Candidato instalado no commit $RESOLVED_SHA."
log "Atalho: TriView Workspace — $CANDIDATE_ID"
log "Atalho: Atualizar TriView Workspace — $CANDIDATE_ID"
log "Atalho: Diagnosticar TriView Workspace — $CANDIDATE_ID"
log "Atalho: Reverter TriView Workspace — $CANDIDATE_ID"
log "Backup anterior: ${backup_dir:-não necessário}"
log "Relatório de troca: $switch_report"
log "Relatório de atalhos: $shortcut_report"
log "Dados: $DATA_ROOT"
log "Estado: $STATE_ROOT"
log "Metadados: $release_dir/candidate-release.json"
