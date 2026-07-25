#!/usr/bin/env bash
set -Eeuo pipefail

HOME_DIR="${HOME:?HOME não definido}"
BACKUP_ROOT="${TRIVIEW_BACKUP_ROOT:-$HOME_DIR/.local/share/triview-workspace-backups}"
LEGACY_APP_DIR="${TRIVIEW_LEGACY_APP_DIR:-$HOME_DIR/.local/share/triview-workspace-linux}"
LEGACY_CONFIG_DIR="${TRIVIEW_LEGACY_CONFIG_DIR:-$HOME_DIR/.config/triview-workspace}"
DRY_RUN=0
ASSUME_YES=0

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --yes) ASSUME_YES=1; shift ;;
    --help|-h)
      printf 'Uso: restore-latest.sh [--dry-run] [--yes]\n'
      exit 0
      ;;
    *) printf 'Opção desconhecida: %s\n' "$1" >&2; exit 2 ;;
  esac
done

latest="$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -r | head -n1)"
[[ -n "$latest" ]] || { printf 'Nenhum backup encontrado em %s\n' "$BACKUP_ROOT" >&2; exit 1; }
backup="$BACKUP_ROOT/$latest"
printf 'Backup selecionado: %s\n' "$backup"

if ((!ASSUME_YES && !DRY_RUN)); then
  printf 'Restaurar a aplicação e a configuração legadas? [s/N] '
  read -r answer
  [[ "$answer" =~ ^[sS]$ ]] || exit 0
fi

if [[ -d "$backup/legacy-app" ]]; then
  if ((DRY_RUN)); then
    printf '[DRY-RUN] restaurar %s para %s\n' "$backup/legacy-app" "$LEGACY_APP_DIR"
  else
    mkdir -p "$LEGACY_APP_DIR"
    cp -a "$backup/legacy-app/." "$LEGACY_APP_DIR/"
  fi
fi

if [[ -d "$backup/legacy-config" ]]; then
  if ((DRY_RUN)); then
    printf '[DRY-RUN] restaurar %s para %s\n' "$backup/legacy-config" "$LEGACY_CONFIG_DIR"
  else
    mkdir -p "$LEGACY_CONFIG_DIR"
    cp -a "$backup/legacy-config/." "$LEGACY_CONFIG_DIR/"
  fi
fi

printf 'Restauração concluída. A nova instalação foi mantida para inspeção.\n'
