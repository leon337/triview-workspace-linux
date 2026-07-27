#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

exec bash "$SCRIPT_DIR/install-module-candidate.sh" \
  "LEA-198-205" \
  "train/road-to-1.0" \
  "triview_workspace.gui_hub"
