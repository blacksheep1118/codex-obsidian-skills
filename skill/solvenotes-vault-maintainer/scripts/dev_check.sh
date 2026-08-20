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
STEP_TIMEOUT="${SOLVENOTES_STEP_TIMEOUT:-180}"

# Prefer an explicitly selected interpreter, otherwise use the interpreter
# visible on PATH. The vault itself remains a pure notes tree; pytest and ruff
# run from this external Skill.
PYTHON_BIN="${SOLVENOTES_PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
elif [[ "$PYTHON_BIN" != */* ]]; then
  # CI commonly exposes the interpreter as the command name ``python``.
  # Resolve that name before checking executability; ``-x python`` tests for
  # a file in the current directory and incorrectly rejects PATH commands.
  PYTHON_BIN="$(command -v "$PYTHON_BIN" || true)"
fi
if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  printf '%s\n' 'No Python interpreter found. Set SOLVENOTES_PYTHON_BIN or activate a virtual environment.' >&2
  exit 2
fi
printf 'python_bin %s\n' "$PYTHON_BIN"

check_environment() {
  local mode="${1:-vault-quick}"
  local -a doctor_args=( \
    "$SKILL_ROOT/scripts/doctor.py" \
    --python-bin "$PYTHON_BIN" \
    --skills-root "$SKILLS_ROOT" \
    --profile "$mode" \
    --strict \
  )
  if [[ -n "$VAULT_ROOT" ]]; then
    doctor_args+=(--notes-root "$VAULT_ROOT")
  fi
  run_step "$PYTHON_BIN" "${doctor_args[@]}"
}

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
Usage: SOLVENOTES_VAULT_ROOT=/path/to/notes bash scripts/dev_check.sh <tool-quick|tool-full|vault-quick|vault-full|quick|full|online|github-ready|gc> [options]

Commands:
  tool-quick    compile and validate the maintenance Skill entry points
  tool-full     run Skill lint and tests; use this in the Skills repository CI
  vault-quick   run fast external-vault content checks
  vault-full    run the complete external-vault content gate
  quick         compatibility alias for vault-quick
  full          compatibility alias for vault-full
  online        read-only external URL audit; results/cache stay outside the vault
  github-ready  vault-full plus repository hygiene, large-file and public checks
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
  VAULT_ROOT="$(cd "$VAULT_ROOT" && pwd -P)"
  export SOLVENOTES_VAULT_ROOT="$VAULT_ROOT"
}

run_step() {
  CURRENT_STEP="$*"
  printf '\n==> %s\n' "$CURRENT_STEP"
  "$PYTHON_BIN" "$SKILL_ROOT/scripts/run_with_timeout.py" \
    --timeout "$STEP_TIMEOUT" --label "$CURRENT_STEP" -- "$@"
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

check_skill_lock() {
  local -a lock_args=(check_skills_lock.py --notes-root "$VAULT_ROOT" --skills-root "$SKILLS_ROOT")
  if git -C "$SKILLS_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    check_script "${lock_args[@]}"
  else
    check_script "${lock_args[@]}" --allow-no-git
  fi
}

check_workspace_guidance() {
  local workspace_root="${SOLVENOTES_WORKSPACE_ROOT:-}"
  if [[ -z "$workspace_root" && -f "$SKILLS_ROOT/../AGENT.md" && -d "$SKILLS_ROOT/../agent" ]]; then
    workspace_root="$(cd "$SKILLS_ROOT/.." && pwd)"
  fi
  if [[ -n "$workspace_root" && -f "$workspace_root/AGENT.md" && -d "$workspace_root/agent" ]]; then
    check_script check_workspace_guidance.py --workspace-root "$workspace_root"
    check_script check_documented_commands.py --workspace-root "$workspace_root" --skills-root "$SKILLS_ROOT" --strict
  else
    printf 'workspace_guidance skipped (workspace-level AGENT.md and agent/ are not available)\n'
  fi
}

tool_quick() {
  if [[ -f "$SKILLS_ROOT/scripts/validate_all.py" ]]; then
    run_step env -u SOLVENOTES_VAULT_ROOT \
      SOLVENOTES_PYTHON_BIN="$PYTHON_BIN" \
      "$PYTHON_BIN" "$SKILLS_ROOT/scripts/validate_all.py" --quick
    return
  fi
  check_environment tool-quick
  run_skill_python -m compileall "$SKILL_ROOT/scripts"
  run_skill_python "$SKILL_ROOT/scripts/validate_skill.py"
}

tool_full() {
  if [[ -f "$SKILLS_ROOT/scripts/validate_all.py" ]]; then
    run_step env -u SOLVENOTES_VAULT_ROOT \
      SOLVENOTES_PYTHON_BIN="$PYTHON_BIN" \
      "$PYTHON_BIN" "$SKILLS_ROOT/scripts/validate_all.py"
    return
  fi
  check_environment tool-full
  run_skill_python -m compileall "$SKILL_ROOT/scripts"
  run_skill_python "$SKILL_ROOT/scripts/validate_skill.py"
  run_skill_python -m ruff check "$SKILL_ROOT/scripts" "$SKILL_ROOT/tests"
  run_skill_python -m pytest -p no:cacheprovider --durations=20 "$SKILL_ROOT/tests"
}

vault_quick() {
  require_vault
  check_environment vault-quick
  check_skill_lock
  check_workspace_guidance
  check_script check_guidance.py
  check_script check_algorithm_job_notes.py
  check_script check_links.py
  check_script check_frontmatter.py
  check_script check_all_notes.py
  check_script check_naturalness.py --strict
  run_step git -C "$VAULT_ROOT" diff --check
}

vault_full() {
  require_vault
  check_environment vault-full
  check_skill_lock
  check_workspace_guidance
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
  local -a changed_scope_args=()
  if [[ -n "${SOLVENOTES_CHANGED_SCOPE_BASE_SHA:-}" ]]; then
    changed_scope_args+=(--base-sha "$SOLVENOTES_CHANGED_SCOPE_BASE_SHA")
  fi
  if [[ -n "${SOLVENOTES_CHANGED_SCOPE_HEAD_SHA:-}" ]]; then
    changed_scope_args+=(--head-sha "$SOLVENOTES_CHANGED_SCOPE_HEAD_SHA")
  fi
  if [[ -n "${SOLVENOTES_CHANGED_SCOPE_MERGE_BASE:-}" ]]; then
    changed_scope_args+=(--merge-base "$SOLVENOTES_CHANGED_SCOPE_MERGE_BASE")
  fi
  if ((${#changed_scope_args[@]})); then
    check_script check_changed_scope.py "${changed_scope_args[@]}"
  else
    check_script check_changed_scope.py
  fi
  run_step git -C "$VAULT_ROOT" diff --check
  if git -C "$SKILLS_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    run_step git -C "$SKILLS_ROOT" diff --check
  else
    printf 'skill_source_git_check skipped installed mirror is not a Git worktree: %s\n' "$SKILLS_ROOT"
  fi
}

github_ready() {
  vault_full
  require_vault
  check_script check_repo_hygiene.py
  check_script check_large_files.py
  check_script check_public_readiness.py --strict
  run_step git -C "$VAULT_ROOT" status --short --branch
}

online() {
  require_vault
  check_environment online
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
  tool-quick) tool_quick ;;
  tool-full) tool_full ;;
  vault-quick|quick) vault_quick ;;
  vault-full|full) vault_full ;;
  online) online "$@" ;;
  github-ready) github_ready ;;
  gc) gc_repo "${@:2}" ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
