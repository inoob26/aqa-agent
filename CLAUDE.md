# CLAUDE.md

The context for working on this repository lives in [AGENTS.md](./AGENTS.md). Read it first.

Claude Code specifics only:

- `.claude/skills` is a symlink to `.agents/skills`, so the skills are live in this
  repository without installing the plugin. To test the plugin packaging itself, start a
  session with `claude --plugin-dir .`.
- Load skills in layers: `SKILL.md` first, files under `references/` only when you need the
  depth. `playwright-automation/references/` alone is ~3600 lines.
- This file is not loaded when the plugin is installed elsewhere; nothing the agent needs at
  run time may live here.
