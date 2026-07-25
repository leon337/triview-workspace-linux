#!/usr/bin/env bash
set -Eeuo pipefail

CANDIDATE_ID="${1:?Informe o identificador, por exemplo LEA-204}"
BRANCH="${2:?Informe a branch do candidato}"
MODULE="${3:?Informe o módulo gráfico, por exemplo triview_workspace.gui_sessions}"
REPO="${TRIVIEW_REPO:-leon337/triview-workspace-linux}"
SAFE_ID="$(printf '%s' "$CANDIDATE_ID" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9._-')"
[[ -n "$SAFE_ID" ]] || { printf 'Identificador inválido.\n' >&2; exit 2; }

APP_ROOT="${TRIVIEW_CANDIDATE_ROOT:-$HOME/.local/share/triview-workspace-candidates/$SAFE_ID}"
DATA_ROOT="${TRIVIEW_CANDIDATE_DATA_ROOT:-$HOME/.local/share/triview-workspace-candidate-data/$SAFE_ID}"
STATE_ROOT="${TRIVIEW_CANDIDATE_STATE_ROOT:-$HOME/.local/state/triview-workspace-candidates/$SAFE_ID}"
BIN_DIR="$HOME/.local/bin"
APPLICATIONS_DIR="$HOME/.local/share/applications"
timestamp="$(date +%Y%m%d-%H%M%S)"
release_dir="$APP_ROOT/releases/$timestamp"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

log() { printf '[TriView Candidate %s] %s\n' "$CANDIDATE_ID" "$*"; }
fail() { log "ERRO: $*" >&2; exit 1; }
for command in curl tar python3; do
  command -v "$command" >/dev/null 2>&1 || fail "$command não encontrado."
done

mkdir -p "$APP_ROOT/releases" "$DATA_ROOT" "$STATE_ROOT" "$BIN_DIR" "$APPLICATIONS_DIR"
archive_url="https://github.com/$REPO/archive/refs/heads/$BRANCH.tar.gz"
log "Baixando $BRANCH..."
curl -fL "$archive_url" -o "$tmp_dir/source.tar.gz"
mkdir -p "$tmp_dir/extracted"
tar -xzf "$tmp_dir/source.tar.gz" -C "$tmp_dir/extracted" --strip-components=1
[[ -f "$tmp_dir/extracted/pyproject.toml" ]] || fail "Pacote inválido."
python3 -m compileall -q "$tmp_dir/extracted/src"
mkdir -p "$release_dir"
cp -a "$tmp_dir/extracted/." "$release_dir/"
export PYTHONPATH="$release_dir/src"
export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
cd "$release_dir"
python3 -m triview_workspace.cli --diagnostic \
  --workspace "$release_dir/config/workspaces/three-mobile.json" \
  --data-file "$DATA_ROOT/diagnostic-workspaces.json" >/dev/null
python3 -c "import importlib; module=importlib.import_module('$MODULE'); assert callable(module.main)"

current_link="$APP_ROOT/current"
temp_link="$APP_ROOT/.current-$timestamp"
ln -s "$release_dir" "$temp_link"
mv -Tf "$temp_link" "$current_link"
launcher="$BIN_DIR/triview-workspace-$SAFE_ID"
cat > "$launcher" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
CURRENT="$current_link"
export XDG_DATA_HOME="$DATA_ROOT"
export XDG_STATE_HOME="$STATE_ROOT"
export PYTHONPATH="\$CURRENT/src\${PYTHONPATH:+:\$PYTHONPATH}"
cd "\$CURRENT"
exec python3 -m "$MODULE"
EOF
chmod +x "$launcher"

desktop="$APPLICATIONS_DIR/triview-workspace-$SAFE_ID.desktop"
cat > "$desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TriView Workspace — $CANDIDATE_ID
Comment=Candidato isolado do trem de desenvolvimento
Exec=$launcher
Icon=preferences-desktop-display
Terminal=false
Categories=Utility;Development;
StartupNotify=true
EOF
chmod +x "$desktop"
update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
log "Candidato instalado. Atalho: TriView Workspace — $CANDIDATE_ID"
log "Dados: $DATA_ROOT"
log "Estado: $STATE_ROOT"
