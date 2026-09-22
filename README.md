# aqa agent

An AI **test automation engineer**. It takes a task description (PRD, user story, ticket,
`git diff`, OpenAPI spec, bug report), derives **test cases** from it, then writes
**executable tests** — in Python (pytest) or TypeScript (Playwright).

Runs in two runtimes — **Claude Code** and **Codex CLI** — from a single source of truth.
The structure mirrors its sibling [`py-devops-agent`](../py-devops-agent).

## Architecture

| Entity | Claude Code | Codex CLI |
|--------|-------------|-----------|
| Agent (persona + tools) | `.claude/agents/aqa.md` | `.codex/agents/aqa.toml` |
| Skills (capabilities) | `.claude/skills/` → symlink | `.agents/skills/` (native) |
| Shared context | `AGENTS.md` + `CLAUDE.md` | `AGENTS.md` |

Skills follow the [open Agent Skills standard](https://agentskills.io): the same `SKILL.md`
works in both tools. The real source is `.agents/skills/`; Claude Code sees it through the
`.claude/skills` symlink. Edit a skill once and it changes everywhere.

> 🪟 **Windows.** The `.claude/skills` symlink is stored in git as a symlink (mode `120000`)
> and works correctly on Linux/macOS. On `git clone` under Windows without symlink support it
> expands into a text stub and Claude Code won't find the skills. Enable support once:
> Developer Mode (or run as admin) + `git config --global core.symlinks true`, then re-clone.
> The real skill files live in `.agents/skills/` and are platform-independent.

## Skills

| Skill | Purpose | Language |
|-------|---------|----------|
| `qa-project-context`     | Stack, frameworks, CI, environments, risks → `.agents/qa-project-context.md`. Read **first** by every other skill | — |
| `test-planning`          | Sprint/release plan: scope, depth, estimation, priorities, risk × effort matrix | — |
| `ai-test-generation`     | The pipeline "task description → requirements → risks → coverage matrix → scenarios → oracles → code", with guardrails against hallucinated APIs and empty assertions | — |
| `playwright-automation`  | E2E: Page Object, fixtures, auto-waiting, locators, parallel execution, sharding, CI | TypeScript |
| `api-testing`            | REST/GraphQL: APIRequestContext, Supertest, Zod/AJV schemas, auth flows, CRUD, pagination | TypeScript |
| `python-test-automation` | pytest: fixtures, parametrization, pytest-playwright, httpx, Pydantic v2 contracts, respx, xdist, Allure | Python |

The agent's order of work: **context → scope → test cases → code → verification**.
Code comes last, after the coverage matrix — details in [AGENTS.md](./AGENTS.md).

### Choosing the language

By the target project's stack, not by preference: `pyproject.toml`/`conftest.py` → Python,
`package.json`/`playwright.config.ts` → TypeScript. A Python backend with a JS frontend gets
API tests in Python and E2E in TypeScript.

The conceptual layer (locator priority, Page Object design, why a schema contract beats a key
check) is the same in both languages — only the syntax differs. That's why
`python-test-automation` points at `playwright-automation`'s reference files instead of
duplicating them.

## Structure

```
aqa-agent/
├── AGENTS.md                       # shared context (both runtimes)
├── CLAUDE.md                       # thin pointer → AGENTS.md
├── README.md
├── pyproject.toml
├── .agents/skills/                 # ★ single source of skills
│   ├── LICENSE.qa-skills           # MIT license of the vendored skills
│   ├── qa-project-context/
│   ├── test-planning/
│   ├── ai-test-generation/
│   ├── playwright-automation/
│   ├── api-testing/
│   └── python-test-automation/     # ours
├── .claude/
│   ├── agents/aqa.md
│   └── skills → ../.agents/skills  # symlink
└── .codex/
    └── agents/aqa.toml
```

## Provenance

Five skills are vendored copies from
[petrkindlmann/qa-skills](https://github.com/petrkindlmann/qa-skills)
(MIT, © 2026 Petr Kindlmann), commit `b3bb61b`. The license text is at
`.agents/skills/LICENSE.qa-skills`.

Local modifications:

- `qa-project-context`: the blank context template, which upstream keeps at its repository
  root, moved to `references/template.md` next to the skill, and the reference in `SKILL.md`
  updated. Without this the skill pointed at a file that doesn't exist in our copy.

`python-test-automation` is ours: the upstream automation skills are written for TypeScript
and mention Python only in passing.

### Updating the vendored skills

```bash
git clone --depth 1 https://github.com/petrkindlmann/qa-skills.git /tmp/qa-skills
for s in qa-project-context test-planning ai-test-generation playwright-automation api-testing; do
  diff -ru ".agents/skills/$s" "/tmp/qa-skills/skills/$s"
done
```

Review the diff before copying: the modification listed above has to be reapplied.

Upstream skills cross-reference each other ("see `test-strategy`", "use `visual-testing`").
We took 6 of 50, so references to the rest remain as text and lead nowhere. If you need
another one, copy its folder from upstream into `.agents/skills/` and add a row to the skills
table in `AGENTS.md` and to the personas (`.claude/agents/aqa.md`, `.codex/agents/aqa.toml`).

## Installation

The agent has three parts: the **persona** (`.md`/`.toml`), the **skills**
(`.agents/skills/`) and the **shared context** (`AGENTS.md`). Skills are the single source of
truth, so when copying it matters that `.claude/skills` stays a symlink instead of being
expanded into a copy.

> ⚠️ `cp -r` dereferences symlinks by default. Use `cp -a` (or `cp -rL` only if you
> deliberately want two independent copies). `git`, `rsync -a` and `tar` preserve symlinks.

### Into a project

```bash
TARGET=/path/to/your-project

cp -a .agents          "$TARGET"/
cp -a .claude          "$TARGET"/   # .claude/skills stays a symlink → ../.agents/skills
cp -a .codex           "$TARGET"/
cp -a AGENTS.md CLAUDE.md "$TARGET"/

# verify the symlink didn't expand into a copy
ls -la "$TARGET"/.claude/skills      # expect: skills -> ../.agents/skills
```

Claude Code only (no Codex) — `.agents/`, `.claude/`, `AGENTS.md`, `CLAUDE.md` are enough.
Codex only — `.agents/`, `.codex/`, `AGENTS.md`.

### Globally (in `~`)

```bash
SRC="$(pwd)"            # root of this repository

# --- Claude Code (~/.claude) ---
mkdir -p ~/.claude/agents
ln -sfn "$SRC/.claude/agents/aqa.md" ~/.claude/agents/aqa.md
ln -sfn "$SRC/.agents/skills"        ~/.claude/skills

# --- Codex CLI (~/.codex) ---
mkdir -p ~/.codex/agents
ln -sfn "$SRC/.codex/agents/aqa.toml" ~/.codex/agents/aqa.toml
ln -sfn "$SRC/.agents/skills"         ~/.codex/skills
```

> ⚠️ Global `~/.claude/skills` is shared by all agents. If it already points at
> `py-devops-agent`'s skills, the second `ln -sfn` overwrites it. Keep one agent's skills
> global and install the other per-project, or build a combined directory of symlinks to the
> individual skills of both repositories.

> Check Codex's global skills path (`~/.codex/skills`) against your CLI version in the
> [Codex documentation](https://developers.openai.com/codex/skills).

To update, `git pull` in `$SRC`; the symlinks see the new version immediately.

## Running

**Claude Code** — invoke the `aqa` subagent. From the monorepo root, via the Makefile:

```bash
make dc-claude repo=aqa-agent
```

**Codex CLI** — `codex` reads `.codex/agents/` and `.agents/skills/` automatically.

The first thing to do in a new target project is to create `.agents/qa-project-context.md`
(the `qa-project-context` skill). Without it every skill re-asks about the stack, the
frameworks and the conventions.

Example requests:

- "Here's a feature description — make a test plan and write E2E tests for checkout"
- "Generate API tests from this OpenAPI spec"
- "Here's a bug report — write a failing regression test"
- "Build a coverage matrix for this user story, don't write code yet"

## Development

```bash
uv sync            # install dependencies
ruff check .       # lint
mypy .             # type check
pytest             # tests
```

> There's no Python code in the repository yet — this is a configuration-only agent. The
> commands matter once skill validation or tests for the skills appear.

## License

MIT, see [LICENSE](./LICENSE) — this covers the agent configuration and the
`python-test-automation` skill. The five vendored skills keep their own upstream MIT
license at `.agents/skills/LICENSE.qa-skills`; see [Provenance](#provenance).
