#!/usr/bin/env bash
set -euo pipefail

SKILL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -d "$SKILL_ROOT/../../scripts" && -d "$SKILL_ROOT/../../skill" ]]; then
  SKILLS_ROOT="$(cd "$SKILL_ROOT/../.." && pwd)"
else
  SKILLS_ROOT="$(cd "$SKILL_ROOT/.." && pwd)"
fi
VAULT_ROOT="${SOLVENOTES_VAULT_ROOT:-}"
if [[ -d "$SKILLS_ROOT/skill/algorithm-job-notes-for-obsidian" ]]; then
  ALGORITHM_SKILL_ROOT="$SKILLS_ROOT/skill/algorithm-job-notes-for-obsidian"
else
  ALGORITHM_SKILL_ROOT="$(cd "$SKILL_ROOT/.." && pwd)/algorithm-job-notes-for-obsidian"
fi
ALGORITHM_SCRIPTS="$ALGORITHM_SKILL_ROOT/scripts"

export PYTHONUNBUFFERED=1
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/solvenotes-pycache}"
export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-/tmp/solvenotes-ruff-cache}"
export PYTHONPATH="$ALGORITHM_SCRIPTS:$SKILL_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"

# Prefer an explicitly selected interpreter or a local Python with the
# repository's development dependencies. The vault itself remains a pure
# notes tree; pytest and ruff run from this external Skill.
PYTHON_BIN="${SOLVENOTES_PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1 || ! "$PYTHON_BIN" -c 'import pytest, ruff' >/dev/null 2>&1; then
  for candidate in /opt/anaconda3/bin/python3 /opt/homebrew/bin/python3; do
    if [[ -x "$candidate" ]] && "$candidate" -c 'import pytest, ruff' >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi
printf 'python_bin %s\n' "$PYTHON_BIN"

CURRENT_STEP=""

on_exit() {
  local status=$?
  if [[ "$status" -ne 0 ]]; then
    if [[ -n "$CURRENT_STEP" ]]; then
      printf '\nFAILED: %s (exit %s)\n' "$CURRENT_STEP" "$status" >&2
    else
      printf '\nFAILED (exit %s)\n' "$status" >&2
    fi
  fi
}
trap on_exit EXIT

usage() {
  cat <<'EOF'
Usage: SOLVENOTES_VAULT_ROOT=/path/to/notes bash scripts/dev_check.sh <quick|full|online|github-ready|gc> [options]

Commands:
  quick         run fast external-vault checks and Skill tests
  full          run the complete external-vault gate
  online        read-only external URL audit; results/cache stay outside the vault
  github-ready  full plus repository hygiene, large-file and public checks
  gc            refuse by default; requires: gc --confirm-prune-now
EOF
}

require_vault() {
  if [[ -z "$VAULT_ROOT" ]]; then
    printf '%s\n' 'SOLVENOTES_VAULT_ROOT must point to the external notes vault.' >&2
    exit 2
  fi
  if [[ ! -d "$VAULT_ROOT" || ! -f "$VAULT_ROOT/AGENT.md" ]]; then
    printf 'invalid SOLVENOTES_VAULT_ROOT: %s\n' "$VAULT_ROOT" >&2
    exit 2
  fi
  export SOLVENOTES_VAULT_ROOT="$VAULT_ROOT"
}

run_step() {
  CURRENT_STEP="$*"
  printf '\n==> %s\n' "$CURRENT_STEP"
  "$@"
  CURRENT_STEP=""
}

run_vault_python() {
  run_step env SOLVENOTES_VAULT_ROOT="$VAULT_ROOT" PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" "$@"
}

run_skill_python() {
  (cd "$SKILL_ROOT" && run_step "$PYTHON_BIN" "$@")
}

run_algorithm_python() {
  run_step env SOLVENOTES_VAULT_ROOT="$VAULT_ROOT" PYTHONPATH="$PYTHONPATH" "$PYTHON_BIN" "$ALGORITHM_SCRIPTS/$1" "${@:2}"
}

check_script() {
  run_vault_python "$SKILL_ROOT/scripts/$1" "${@:2}"
}

quick() {
  require_vault
  run_skill_python -m pytest -p no:cacheprovider "$SKILL_ROOT/tests"
  check_script check_guidance.py
  check_script check_algorithm_job_notes.py
  check_script check_links.py
  check_script check_frontmatter.py
  check_script check_all_notes.py
  check_script check_naturalness.py --strict
  run_step git -C "$VAULT_ROOT" diff --check
}

full() {
  require_vault
  check_script check_all_notes.py
  check_script check_algorithm_job_notes.py
  check_script check_guidance.py
  check_script check_links.py
  check_script check_source_coverage.py
  check_script check_examples.py
  check_script check_python_examples.py --root "$VAULT_ROOT"
  run_algorithm_python check_cpp_examples.py --root "$VAULT_ROOT"
  check_script check_paper_notes.py
  check_script analyze_example_quality.py --strict
  check_script check_naturalness.py --strict
  check_script check_language_rigor.py --strict
  check_script check_frontmatter.py
  check_script check_markdown_tables.py
  check_script check_formulas.py
  check_script check_headings.py
  check_script check_special_dirs.py
  check_script normalize_source_manifests.py --check
  check_script wrap_source_coverage_blocks.py --check
  check_script sync_note_frontmatter.py --check
  check_script check_changed_scope.py --base origin/main
  run_skill_python -m compileall "$SKILL_ROOT/scripts"
  run_skill_python -m ruff check --cache-dir "$RUFF_CACHE_DIR" "$SKILL_ROOT/scripts" "$SKILL_ROOT/tests"
  run_skill_python -m pytest -p no:cacheprovider "$SKILL_ROOT/tests"
  run_step git -C "$VAULT_ROOT" diff --check
  if git -C "$SKILLS_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    run_step git -C "$SKILLS_ROOT" diff --check
  else
    printf 'skill_source_git_check skipped installed mirror is not a Git worktree: %s\n' "$SKILLS_ROOT"
  fi
}

github_ready() {
  full
  require_vault
  check_script check_repo_hygiene.py
  check_script check_large_files.py
  check_script check_public_readiness.py --strict
  run_step git -C "$VAULT_ROOT" status --short --branch
}

online() {
  require_vault
  local -a extra_args=("${@:2}")
  local has_json_out=0
  local argument
  for argument in "${extra_args[@]}"; do
    if [[ "$argument" == "--json-out" || "$argument" == --json-out=* ]]; then
      has_json_out=1
      break
    fi
  done
  if [[ "$has_json_out" -eq 1 ]]; then
    check_script check_external_sources.py --root "$VAULT_ROOT" "${extra_args[@]}"
  else
    check_script check_external_sources.py --root "$VAULT_ROOT" \
      --json-out "${SOLVENOTES_ONLINE_JSON_OUT:-/tmp/solvenotes-external-sources.json}" \
      "${extra_args[@]}"
  fi
}

gc_repo() {
  local confirmation="${1:-}"
  if [[ "$#" -ne 1 || "$confirmation" != "--confirm-prune-now" ]]; then
    printf '%s\n' \
      'REFUSED: destructive pruning requires explicit user authorization and gc --confirm-prune-now.' >&2
    return 2
  fi
  run_step git -C "$SKILLS_ROOT" gc --prune=now
  run_step git -C "$SKILLS_ROOT" count-objects -vH
}

command="${1:-}"
case "$command" in
  quick) quick ;;
  full) full ;;
  online) online "$@" ;;
  github-ready) github_ready ;;
  gc) gc_repo "${@:2}" ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
