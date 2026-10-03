# AGENTS.md

Context for AI agents **working on this repository** (Claude Code and Codex CLI).
This file is not shipped to target projects: the rules the `aqa` agent follows there live in
the `aqa-workflow` skill.

## What this repository is

The source of one agent, `aqa` — a test automation engineer that turns a task description
into reviewed test cases and then into executable tests. It ships as a Claude Code plugin
and as a Codex agent from a single source.

| Path | What | Edit? |
|------|------|-------|
| `.agents/skills/` | All skills — the single source for both runtimes | yes |
| `persona/aqa.md` | The persona — single source | yes |
| `.claude/agents/aqa.md`, `.codex/agents/aqa.toml` | Generated personas | no — run `scripts/build_personas.py` |
| `.claude-plugin/` | Plugin and marketplace manifests | yes |
| `hooks/hooks.json`, `.mcp.json` | Plugin hook (lint on write) and Playwright MCP server | yes |
| `.agents/skills/aqa-verify/scripts/aqa_lint.py` | The linter the agent and the hook run | yes, with tests |
| `tests/` | Linter tests and repository consistency checks | yes |
| `evals/` | Behavioral eval cases for `claude plugin eval` | yes |
| `templates/` | Files a target project copies (CI workflow, settings) | yes |

## Skills

| Kind | Skills |
|------|--------|
| Ours | `aqa-workflow` (the rules), `aqa-cases`, `aqa-generate`, `aqa-verify` (entry points), `python-test-automation` |
| Vendored from [qa-skills](https://github.com/petrkindlmann/qa-skills) (MIT) | `qa-project-context`, `test-planning`, `ai-test-generation`, `unit-testing`, `playwright-automation`, `api-testing`, `test-reliability` |

Rules for changing them:

- Keep vendored skills as close to upstream as possible. Every local modification is listed
  in README → Provenance; add yours there.
- Agent-wide rules go into `aqa-workflow`, not into the persona and not into several skills.
  The persona stays a thin pointer.
- A new skill needs: a directory under `.agents/skills/`, a mention in `persona/aqa.md`, in
  `aqa-workflow` and in the README skills table. `tests/test_repo.py` fails until all are done.
- A rule that can be checked mechanically belongs in `aqa_lint.py` with a test, not only in
  prose.

## Commands

```bash
uv sync                                  # dev dependencies
uv run pytest                            # linter tests + repository consistency
uv run ruff check . && uv run mypy       # lint and types
python3 scripts/build_personas.py        # regenerate personas after editing persona/aqa.md
claude plugin validate .                 # manifests
claude plugin eval . --scaffold --allow-tools Write Edit Bash --ablation none --runs 1
```

Evals call the model on your account; run a single case with `--case <name>` while iterating.

## Boundaries

- Do not edit the generated personas by hand.
- Do not add a `model` pin to the Codex persona; it follows the user's profile.
- Bump `version` in `.claude-plugin/plugin.json` and `pyproject.toml` together.
