#!/usr/bin/env bash
set -euo pipefail

SKILLS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VAULT_ROOT="${SOLVENOTES_VAULT_ROOT:-$(git rev-parse --show-toplevel)}"

SOLVENOTES_VAULT_ROOT="$VAULT_ROOT" \
  bash "$SKILLS_ROOT/skill/solvenotes-vault-maintainer/scripts/dev_check.sh" quick
