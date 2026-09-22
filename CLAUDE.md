# CLAUDE.md

The project's main context lives in [AGENTS.md](./AGENTS.md). Read it first.

Claude Code specifics only:

- The subagent is defined in `.claude/agents/aqa.md`.
- Skills are reachable through the `.claude/skills → .agents/skills` symlink (single source
  of truth).
- Load skills in layers: `SKILL.md` first, files under `references/` only when you need the
  depth. Don't pull all of `playwright-automation/references/` (~3600 lines) into context for
  one test.
- Delegate narrow tasks to skills instead of holding everything in one context.
