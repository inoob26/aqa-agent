# aqa agent

An AI **test automation engineer**. It takes a task description (PRD, user story, ticket,
`git diff`, OpenAPI spec, bug report), derives **test cases** from it, stops for a human
review, then writes **executable tests** — in Python (pytest) or TypeScript (Playwright) —
and proves each one fails when the behavior it covers is broken.

Runs in two runtimes from a single source: **Claude Code** (as a plugin) and **Codex CLI**.

## How it works

```
task description ──► aqa-cases ──► .agents/aqa/<slug>/coverage.md (draft)
                                         │
                                  human review  ◄── the gate: the agent never approves
                                         │           its own matrix
                                         ▼
                     aqa-generate ──► tests with `Scenario: SC-NNN` references
                                         │
                                         ▼
                     aqa-verify ───► lint · traceability · parallel run · mutation check
                                     └─► .agents/aqa/<slug>/verification.md
```

The intermediate artifacts — requirements, risks, the coverage matrix, scenarios, oracles —
are files in the target project, committed next to the tests. The rules the agent follows
(order of work, file formats, traceability, how to mutate without touching the product,
hard prohibitions) are one skill: [`aqa-workflow`](.agents/skills/aqa-workflow/SKILL.md).

## Install

### Claude Code — plugin

```bash
claude plugin marketplace add inoob26/aqa-agent
claude plugin install aqa@aqa-agent
```

The plugin brings the `aqa` agent, the skills (as `/aqa:aqa-cases`, `/aqa:aqa-generate`, …),
a `PostToolUse` hook that lints every test file as it is written, and the Playwright MCP
server for looking up real selectors in a running app. Nothing is copied into your project
and your `AGENTS.md` / `CLAUDE.md` are not touched.

To try it from a checkout without installing: `claude --plugin-dir /path/to/aqa-agent`.

Optional, in the target project: merge [`templates/claude-settings.json`](templates/claude-settings.json)
into `.claude/settings.json` to pre-approve the commands the agent runs (test runners,
linters, `git diff`, `gh pr view`). A plugin cannot ship permissions, so this is a manual step.

### Codex CLI, or Claude Code without the plugin

```bash
scripts/install.sh /path/to/your-project            # both runtimes
scripts/install.sh /path/to/your-project --codex    # Codex only
```

This copies the skills to `<project>/.agents/skills/` and the persona to
`.codex/agents/aqa.toml` and/or `.claude/agents/aqa.md`. It never touches the project's
`AGENTS.md` or `CLAUDE.md`. Re-run it to update.

**Without the plugin**, add by hand what the plugin would have provided:

- the lint hook — merge [`templates/claude-hooks.json`](templates/claude-hooks.json) into
  `.claude/settings.json`;
- the Playwright MCP server — `claude mcp add playwright -- npx @playwright/mcp@latest`.

> Check the Codex paths (`.codex/agents/`, `.agents/skills/`) against your CLI version in
> the [Codex documentation](https://developers.openai.com/codex/skills). The Codex persona
> pins no model; it uses the one in your Codex profile.

## Use

The first thing to do in a new target project is `qa-project-context`: it writes
`.agents/qa-project-context.md`, and every other skill reads it instead of re-asking about
the stack and conventions.

| You say | What runs |
|---------|-----------|
| "Test cases for docs/prd/checkout.md" · "Cover this PR" · `/aqa:aqa-cases SHOP-42` | `aqa-cases` → artifacts + a draft matrix, then stops |
| "Approved, write the tests" · `/aqa:aqa-generate shop-42` | `aqa-generate` → tests, lint, traceability |
| "Check they can fail" · `/aqa:aqa-verify shop-42` | `aqa-verify` → runs, mutation check, `verification.md` |
| "Here's a bug report — regression test, no review round" | all three; the red test is the deliverable |
| "Plan testing for the sprint" | `test-planning` |
| "This test fails one run in ten" | `test-reliability` |

Inputs are read from where they live: a file, `gh issue view`, `gh pr diff`, `git diff
main...HEAD`. Jira or Linear tickets are read through that tracker's MCP server if you have
one connected; otherwise paste the text.

### In CI

[`templates/github/aqa.yml`](templates/github/aqa.yml) runs the agent on pull requests:
the label `aqa` produces the test cases and posts the matrix as a comment; the label
`aqa:approved` — applied by a human, which is the review gate — writes the tests and
commits them to the PR branch. It is plain `claude -p --plugin-dir … --agent aqa:aqa`, so
the same command works in any CI system.

## Skills

Single source: `.agents/skills/` ([Agent Skills standard](https://agentskills.io)). Claude
Code sees them through the plugin manifest (and, inside this repository, through the
`.claude/skills` symlink); Codex reads `.agents/skills/` natively.

| Skill | Purpose | Origin |
|-------|---------|--------|
| `aqa-workflow`           | The agent's rules: order of work, artifact contract, traceability, mutation check, prohibitions | ours |
| `aqa-cases`              | Task description → requirements, risks, coverage matrix, scenarios, oracles. Stops for review | ours |
| `aqa-generate`           | Approved matrix → test code with traceability | ours |
| `aqa-verify`             | Lint, traceability, parallel run, mutation check. Ships `aqa_lint.py` | ours |
| `python-test-automation` | Python: pytest, pytest-playwright, httpx, Pydantic v2 contracts, respx, xdist | ours |
| `qa-project-context`     | Stack, frameworks, CI, environments, risks → `.agents/qa-project-context.md` | vendored |
| `test-planning`          | Sprint/release plan: scope, depth, estimation, priorities | vendored |
| `ai-test-generation`     | Extraction, risk analysis, scenario and oracle techniques | vendored |
| `unit-testing`           | Unit tests in pytest/Jest/Vitest, test doubles, mutation testing | vendored |
| `playwright-automation`  | TypeScript E2E: Page Object, fixtures, locators, sharding, CI | vendored |
| `api-testing`            | TypeScript API: APIRequestContext, Supertest, Zod/AJV | vendored |
| `test-reliability`       | Flaky tests: classification, healing, quarantine | vendored |

### The linter

[`aqa_lint.py`](.agents/skills/aqa-verify/scripts/aqa_lint.py) turns the agent's
prohibitions from prose into exit codes. Standard library only, so it runs in any project.

```bash
aqa_lint.py lint  tests/                        # fixed sleeps, retries, .only, secrets, empty asserts
aqa_lint.py trace .agents/aqa/<slug> tests/     # every test ↔ a matrix row, both directions
aqa_lint.py gate  .agents/aqa/<slug>            # is the matrix approved?
```

## Repository layout

```
aqa-agent/
├── .claude-plugin/                 # plugin.json, marketplace.json
├── .agents/skills/                 # ★ single source of skills
├── persona/aqa.md                  # ★ single source of the persona
├── .claude/agents/aqa.md           # generated
├── .codex/agents/aqa.toml          # generated
├── .claude/skills → ../.agents/skills
├── hooks/hooks.json                # plugin hook: lint test files on write
├── .mcp.json                       # plugin MCP server: Playwright
├── scripts/                        # build_personas.py, install.sh
├── templates/                      # for target projects: CI workflow, settings, hooks
├── tests/                          # linter tests, repository consistency
└── evals/                          # behavioral cases for `claude plugin eval`
```

> 🪟 **Windows.** `.claude/skills` is a git symlink (mode `120000`). It only matters when
> working inside this repository; the plugin and `install.sh` do not depend on it. To clone
> with symlinks: Developer Mode + `git config --global core.symlinks true`.

## Development

```bash
uv sync
uv run pytest                          # linter + repository consistency
uv run ruff check . && uv run mypy
python3 scripts/build_personas.py      # after editing persona/aqa.md
claude plugin validate .
```

### Evals

`evals/` holds behavioral cases run against a small fixture project (`evals/_shop/`, a
discount function with one seeded bug):

| Case | Asserts |
|------|---------|
| `cases-stop-at-gate` | A story becomes artifacts on disk with a `draft` matrix; no test code; the reply asks for review |
| `generate-blocked-by-draft` | With a draft matrix the agent writes no tests and does not approve it itself |
| `generate-from-approved` | An approved matrix becomes tests that reference every `SC-NNN`; product code untouched |
| `bug-report-keeps-product` | A bug report yields a regression test; the bug is reported, not fixed |

```bash
claude plugin eval . --scaffold --allow-tools Write Edit Bash --ablation none --runs 1
claude plugin eval . --scaffold --allow-tools Write Edit Bash --case cases-stop-at-gate --runs 1
```

Evals call the model on your account. `--scaffold` runs the fixture scripts; Bash runs in
Claude Code's sandbox (Linux needs `bubblewrap` and `socat`). The fixture has no pytest
installed, so the cases check what is written, not test results.

## Provenance

Seven skills are vendored from
[petrkindlmann/qa-skills](https://github.com/petrkindlmann/qa-skills)
(MIT, © 2026 Petr Kindlmann), commit `b3bb61b`. The license text is at
`.agents/skills/LICENSE.qa-skills`.

Local modifications:

- `qa-project-context`: the blank context template, which upstream keeps at its repository
  root, moved to `references/template.md` next to the skill, and the reference in `SKILL.md`
  updated.
- `ai-test-generation`: hardcoded model names in "Model selection per step" and "Done When"
  replaced with tier descriptions — the names go stale faster than the skill.

Upstream skills cross-reference siblings we did not take (7 of 50 are here). Those names
stay in the vendored text; `aqa-workflow` tells the agent to treat such a reference as out
of scope rather than stop, and `tests/test_repo.py` keeps the list of known absent names.
Where upstream and our rules disagree — `test-reliability` uses retries as a detection
signal in quarantine — `aqa-workflow` wins and the linter requires an explicit
`aqa: allow-retries <ticket>` marker.

### Updating the vendored skills

```bash
git clone --depth 1 https://github.com/petrkindlmann/qa-skills.git /tmp/qa-skills
for s in qa-project-context test-planning ai-test-generation unit-testing \
         playwright-automation api-testing test-reliability; do
  diff -ru ".agents/skills/$s" "/tmp/qa-skills/skills/$s"
done
```

Review the diff before copying: the modifications listed above have to be reapplied. To add
another upstream skill, copy its folder into `.agents/skills/` and follow the checklist in
[AGENTS.md](./AGENTS.md).

## License

MIT, see [LICENSE](./LICENSE) — this covers the agent configuration, the scripts and our
five skills. The vendored skills keep their upstream MIT license at
`.agents/skills/LICENSE.qa-skills`.
