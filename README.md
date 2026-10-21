# aqa-agent

A Claude Code plugin for test design and Playwright test automation.

| Command | Input | Output |
|---|---|---|
| `/aqa-agent:test-cases` | task text, OpenSpec / Spec Kit spec, ADR, OpenAPI — one or many | `.agents/aqa/<slug>/` requirements, test cases, coverage, questions (`status: draft`) |
| `/aqa-agent:bdd` | `<slug>` (approved) | `tests/features/<slug>/*.feature` for playwright-bdd |
| `/aqa-agent:api-tests` | `<slug>` (approved) | Playwright API tests (TS): BDD steps or `*.spec.ts` |
| `/aqa-agent:playwright-tests` | `<slug>` (approved) | Playwright UI tests (TS): BDD steps or `*.spec.ts` |
| `/aqa-agent:verify` | `<slug>` | test run, mutation check, `report.md` |

The plugin also has the `aqa-agent` subagent, the shared `workflow` skill (rules and
templates), the `scripts/aqa_lint.py` checker, and a Playwright MCP server in `.mcp.json`.

## Flow

```
/aqa-agent:test-cases openspec/changes/add-password-reset api/openapi.yaml docs/adr/0007-rate-limits.md
# review .agents/aqa/add-password-reset/, answer questions.md, set status: approved
/aqa-agent:bdd add-password-reset                 # optional
/aqa-agent:api-tests add-password-reset
/aqa-agent:playwright-tests add-password-reset --url http://localhost:3000
/aqa-agent:verify add-password-reset
```

Free text also works: `/aqa-agent:test-cases "users can reset the password by email" --slug pw-reset`.

## Artifacts

The commands keep the design files for one feature in `.agents/aqa/<slug>/` in the target
project. The slug comes from the OpenSpec change name, the Spec Kit feature folder, the ADR
file name, or the task text. The `--slug <name>` argument sets it directly.

### Why `.agents/aqa/`

- **One fixed place.** The `bdd`, `api-tests`, `playwright-tests` and `verify` commands read
  the test cases and check the review gate there.
- **Not test code.** The test runner and the linters do not read the folder, because it is
  outside `tests/`.
- **Not tied to one tool.** Other AI agents also use the `.agents/` folder name.
- **Kept in git.** Commit the folder, so that a reviewer can approve the test cases in a
  pull request.

### Files

| File | Written by | Content |
|---|---|---|
| `requirements.md` | `test-cases` | The sources (`S1`, `S2`…) and the testable requirements `REQ-N`, each with its source |
| `test-cases.md` | `test-cases` | Front matter with `status`, then the `TC-NNN` cases: requirement, priority, layer, technique, preconditions, test data, steps, expected result |
| `coverage.md` | `test-cases`, then each generator | One row for each TC: `auto`, `manual`, `deferred` or `removed`, the test file, and notes (reasons, `BUG:` lines) |
| `questions.md` | `test-cases` | The gaps and conflicts in the inputs (`Q-N`), and the cases that each question blocks |
| `results.json` | `verify` | The Playwright JSON report of the last run |
| `mutations.json` | `verify` | The result of the mutation check for each test |
| `report.md` | `verify` | The result for each TC and each REQ, the mutation score, and the findings |

The templates are in `skills/workflow/templates/`. `aqa_lint.py` reads these files, so
keep the headings and the table columns as the templates show them.

### Review gate

1. `/aqa-agent:test-cases` writes `test-cases.md` with `status: draft`.
2. A person reads the cases, answers `questions.md`, and edits the cases if necessary.
3. The person sets the front matter in `test-cases.md`:

   ```yaml
   status: approved
   approved_by: <name>
   approved_at: <YYYY-MM-DD>
   ```

4. `bdd`, `api-tests` and `playwright-tests` run `aqa_lint.py gate` first. They stop while
   the status is `draft`.

The commands never set `approved`. If you run `/aqa-agent:test-cases` again for the same
slug, it asks you first. A new version of the file starts again as `draft`, and the TC
IDs do not change.

### Change the folder

The path is a convention in the skill text. It is not a setting. `aqa_lint.py` takes the
folder as an argument, so the script needs no change. To use a different folder, for
example `docs/qa/<slug>/`:

1. Replace `.agents/aqa` in these files:

   ```bash
   grep -rlF '.agents/aqa' skills agents README.md \
     | xargs sed -i 's#\.agents/aqa#docs/qa#g'
   ```

2. Move the existing artifact folders in the target projects to the new path.

## Install

Local test of the plugin:

```bash
git clone https://github.com/inoob26/aqa-agent.git
claude --plugin-dir ./aqa-agent
```

## Lint script

```bash
python3 scripts/aqa_lint.py gate   .agents/aqa/<slug>
python3 scripts/aqa_lint.py cases  .agents/aqa/<slug>
python3 scripts/aqa_lint.py trace  .agents/aqa/<slug> tests/api --layer api
python3 scripts/aqa_lint.py lint   tests/api tests/features
python3 scripts/aqa_lint.py report .agents/aqa/<slug> --results .agents/aqa/<slug>/results.json
```

Python 3.10 or later, standard library only. Exit code 0 = OK, 1 = check failed, 2 = usage error.

## Layout

```
.claude-plugin/plugin.json
.mcp.json                         Playwright MCP server
agents/aqa-agent.md               subagent
scripts/aqa_lint.py               gate, cases, trace, lint, report
skills/
  workflow/                       shared rules (not a slash command)
    SKILL.md
    templates/                    requirements.md, test-cases.md, coverage.md, questions.md
    references/scaffold.md        Playwright + playwright-bdd setup
  test-cases/                     + references/inputs.md, references/techniques.md
  bdd/
  api-tests/
  playwright-tests/
  verify/
```
