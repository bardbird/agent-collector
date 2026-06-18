#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL_DEST_DIR="${EVAL_SKILLS_DIR:-$ROOT_DIR/samples/eval_workspace/skills}"
CLAUDE_DEST_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
INSTALL_CLAUDE_SKILLS="${INSTALL_CLAUDE_SKILLS:-1}"
PRUNE="${PRUNE_SKILLS:-1}"
SKILLS_CSV="${EVAL_SKILLS:-}"

usage() {
  cat <<'EOF'
Usage:
  scripts/install_eval_skills.sh --skills skill-a,skill-b [--dest DIR] [--no-claude] [--no-prune]

Required:
  --skills / EVAL_SKILLS   Explicit small skill allowlist for this capture run.

Examples:
  scripts/install_eval_skills.sh --skills warehouse-safety-audit,screenshot-annotator
  INSTALL_CLAUDE_SKILLS=0 EVAL_SKILLS=warehouse-safety-audit scripts/install_eval_skills.sh

By default the script prunes destination skill directories before installing the allowlist, so Claude Code does not see the whole skill pool.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skills)
      SKILLS_CSV="${2:?--skills requires comma-separated names}"
      shift 2
      ;;
    --dest)
      EVAL_DEST_DIR="${2:?--dest requires a directory}"
      shift 2
      ;;
    --claude-dest)
      CLAUDE_DEST_DIR="${2:?--claude-dest requires a directory}"
      shift 2
      ;;
    --no-claude)
      INSTALL_CLAUDE_SKILLS=0
      shift
      ;;
    --no-prune)
      PRUNE=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$SKILLS_CSV" ]]; then
  printf 'error: explicit --skills allowlist is required; refusing to install all skills\n' >&2
  usage >&2
  exit 2
fi

IFS=',' read -r -a SKILLS <<< "$SKILLS_CSV"

install_one() {
  local src="$1"
  local dest_root="$2"
  local skill
  skill="$(basename "$src")"
  mkdir -p "$dest_root"
  rm -rf "$dest_root/$skill"
  cp -R "$src" "$dest_root/$skill"
}

prune_dest() {
  local dest_root="$1"
  [[ "$PRUNE" == "1" ]] || return 0
  mkdir -p "$dest_root"
  find "$dest_root" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +
}

prune_dest "$EVAL_DEST_DIR"
if [[ "$INSTALL_CLAUDE_SKILLS" == "1" ]]; then
  prune_dest "$CLAUDE_DEST_DIR"
fi

installed=0
for skill in "${SKILLS[@]}"; do
  skill="${skill//[[:space:]]/}"
  [[ -n "$skill" ]] || continue
  skill_dir="$ROOT_DIR/skills/$skill"
  if [[ ! -f "$skill_dir/SKILL.md" ]]; then
    printf 'error: missing skill: %s (%s/SKILL.md not found)\n' "$skill" "$skill_dir" >&2
    exit 1
  fi
  install_one "$skill_dir" "$EVAL_DEST_DIR"
  if [[ "$INSTALL_CLAUDE_SKILLS" == "1" ]]; then
    install_one "$skill_dir" "$CLAUDE_DEST_DIR"
  fi
  installed=$((installed + 1))
done

printf '[skills] installed %s skill(s) to %s\n' "$installed" "$EVAL_DEST_DIR"
if [[ "$INSTALL_CLAUDE_SKILLS" == "1" ]]; then
  printf '[skills] installed %s skill(s) to Claude Code: %s\n' "$installed" "$CLAUDE_DEST_DIR"
else
  printf '[skills] skipped Claude Code install (INSTALL_CLAUDE_SKILLS=0)\n'
fi
