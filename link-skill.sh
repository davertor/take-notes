#!/usr/bin/env bash
#
# link-skill.sh — symlink skills/take-notes into one or all AI coding tools'
# skills directories, so a `git pull` in this checkout updates it everywhere.
#
# Source: <this repo>/skills/take-notes
# Targets (canonical global skill-discovery path for each tool):
#   claude   ~/.claude/skills/          codex     ~/.codex/skills/
#   cursor   ~/.cursor/skills/          opencode  ~/.config/opencode/skills/
#   gemini   ~/.gemini/skills/          agents    ~/.agents/skills/
#
# With no AGENT, links all of them. Set AGENT to link only that one, e.g.:
#   AGENT=codex ~/take-notes/link-skill.sh
#
# Policy: if a target already has something named take-notes — a real
# directory, a file, or a symlink pointing elsewhere — it is OVERWRITTEN with
# a symlink back to this checkout. A symlink that's already correct is left
# alone. Safe to re-run any time, e.g. after moving or re-cloning this repo.

set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/take-notes"
if [[ ! -f "$SRC_DIR/SKILL.md" ]]; then
  printf 'error: %s/SKILL.md not found.\n' "$SRC_DIR" >&2
  printf '       Run this script from a clone of the take-notes repo.\n' >&2
  exit 1
fi

AGENT_NAMES=(claude codex cursor opencode gemini agents)
AGENT_DIRS=(
  "$HOME/.claude/skills"
  "$HOME/.codex/skills"
  "$HOME/.cursor/skills"
  "$HOME/.config/opencode/skills"
  "$HOME/.gemini/skills"
  "$HOME/.agents/skills"
)

TARGETS=("${AGENT_DIRS[@]}")
if [[ -n "${AGENT:-}" ]]; then
  TARGETS=()
  for i in "${!AGENT_NAMES[@]}"; do
    [[ "${AGENT_NAMES[$i]}" == "$AGENT" ]] && TARGETS=("${AGENT_DIRS[$i]}")
  done
  if [[ ${#TARGETS[@]} -eq 0 ]]; then
    printf 'error: unknown AGENT "%s". Choose one of: %s\n' "$AGENT" "${AGENT_NAMES[*]}" >&2
    exit 1
  fi
fi

linked=0
replaced=0
skipped=0

for target in "${TARGETS[@]}"; do
  mkdir -p "$target"
  dest="$target/take-notes"

  # Already the correct symlink — nothing to do.
  if [[ -L "$dest" && "$(readlink "$dest")" == "$SRC_DIR" ]]; then
    ((skipped++)) || true
    continue
  fi

  # Anything else occupying the path gets replaced.
  if [[ -e "$dest" || -L "$dest" ]]; then
    rm -rf -- "$dest"
    ln -s "$SRC_DIR" "$dest"
    printf '~ %s (replaced)\n' "$dest"
    ((replaced++)) || true
    continue
  fi

  ln -s "$SRC_DIR" "$dest"
  printf '+ %s\n' "$dest"
  ((linked++)) || true
done

printf '\nDone: %d created, %d replaced, %d already linked.\n' "$linked" "$replaced" "$skipped"
