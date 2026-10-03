#!/usr/bin/env bash
# Install the aqa agent into a target project without the Claude Code plugin system.
#
#   scripts/install.sh <target-project> [--codex] [--claude]     (default: both)
#
# Copies skills to <target>/.agents/skills/ and the persona for each runtime. It never
# touches the target's AGENTS.md or CLAUDE.md: the agent's rules live in the aqa-workflow
# skill. Re-run to update; skills of the same name are replaced, others are left alone.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="" CODEX=0 CLAUDE=0

for arg in "$@"; do
  case "$arg" in
    --codex) CODEX=1 ;;
    --claude) CLAUDE=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) TARGET="$arg" ;;
  esac
done
[ -n "$TARGET" ] || { echo "usage: $0 <target-project> [--codex] [--claude]" >&2; exit 2; }
[ -d "$TARGET" ] || { echo "not a directory: $TARGET" >&2; exit 2; }
[ "$CODEX" = 1 ] || [ "$CLAUDE" = 1 ] || { CODEX=1; CLAUDE=1; }
TARGET="$(cd "$TARGET" && pwd)"

mkdir -p "$TARGET/.agents/skills"
for skill in "$SRC"/.agents/skills/*/; do
  name="$(basename "$skill")"
  rm -rf "${TARGET:?}/.agents/skills/$name"
  cp -a "$skill" "$TARGET/.agents/skills/$name"
done
cp -a "$SRC/.agents/skills/LICENSE.qa-skills" "$TARGET/.agents/skills/"
echo "skills  -> $TARGET/.agents/skills/"

if [ "$CODEX" = 1 ]; then
  mkdir -p "$TARGET/.codex/agents"
  cp -a "$SRC/.codex/agents/aqa.toml" "$TARGET/.codex/agents/aqa.toml"
  echo "codex   -> $TARGET/.codex/agents/aqa.toml"
fi

if [ "$CLAUDE" = 1 ]; then
  mkdir -p "$TARGET/.claude/agents"
  cp -a "$SRC/.claude/agents/aqa.md" "$TARGET/.claude/agents/aqa.md"
  echo "claude  -> $TARGET/.claude/agents/aqa.md"
  # Claude Code reads skills from .claude/skills/. Link each skill individually so the
  # target's own skills in that directory are kept.
  if [ -L "$TARGET/.claude/skills" ]; then
    echo "claude  -> .claude/skills is a symlink, left as is: $(readlink "$TARGET/.claude/skills")"
  else
    mkdir -p "$TARGET/.claude/skills"
    for skill in "$SRC"/.agents/skills/*/; do
      name="$(basename "$skill")"
      ln -sfn "../../.agents/skills/$name" "$TARGET/.claude/skills/$name"
    done
    echo "claude  -> $TARGET/.claude/skills/<skill> (symlinks)"
  fi
  cat <<'NOTE'

Not installed by this script (the plugin does it for you): the PostToolUse lint hook and
the Playwright MCP server. To add them by hand, see "Without the plugin" in README.md.
NOTE
fi
