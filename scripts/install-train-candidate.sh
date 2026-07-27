#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

exec "$SCRIPT_DIR/install-candidate.sh" \
  "LEA-198-205" \
  "leonpcsn/integrate-lea-198-205-unified-candidate"
