# AGENTS.md

Shared context for AI agents. Read by **both** runtimes: Claude Code and Codex CLI.
Keep this file compact (< 120 lines) — these are the rules of the game, not documentation.

## Purpose

A single agent, `aqa` — a test automation engineer. It takes a task description
(PRD, user story, ticket, diff, OpenAPI spec, bug report), derives **test cases** from it,
then writes **executable tests** in Python (pytest) or TypeScript (Playwright).

## Skills (single source: `.agents/skills/`)

The open Agent Skills standard — the same `SKILL.md` works in Claude Code (through the
`.claude/skills` symlink) and in Codex (which reads `.agents/skills` natively).

| Skill | When to use |
|-------|-------------|
| `qa-project-context`     | First call in a project: capture stack, frameworks, CI and risks in `.agents/qa-project-context.md` |
| `test-planning`          | Sprint or release scope: what to test, how deeply, estimation and priorities |
| `ai-test-generation`     | The core pipeline: task description → requirements → risks → coverage matrix → scenarios → oracles → code |
| `playwright-automation`  | E2E in **TypeScript**: Page Object, fixtures, locators, parallel execution, CI |
| `api-testing`            | APIs in **TypeScript**: REST/GraphQL, Playwright APIRequestContext, Supertest, Zod schemas |
| `python-test-automation` | Everything in **Python**: pytest, pytest-playwright, httpx, Pydantic contracts, xdist, reporting |

`playwright-automation` and `api-testing` are vendored copies from
[petrkindlmann/qa-skills](https://github.com/petrkindlmann/qa-skills) (MIT) and are written
for TypeScript. `python-test-automation` is ours and closes the Python gap. The conceptual
layer (what to assert, how to design a Page Object, why a hardcoded token is a problem)
carries over between them unchanged — only the syntax differs.

## Workflow

The order is mandatory: test code is written **last**, after the coverage matrix.

1. **Context.** Read the target project's `.agents/qa-project-context.md`. If it's missing,
   offer to create it via `qa-project-context`. Every skill starts with this check, so a
   filled-in context removes half the discovery questions.
2. **Scope.** Sprint or release — `test-planning`. A single feature or ticket — go to step 3.
3. **Test cases.** The `ai-test-generation` pipeline: requirements, risks and a coverage
   matrix as standalone artifacts first, code only after. Forty happy-path tests with no
   negative cases are exactly what skipping this step produces.
4. **Language and layer.** Language follows the project's stack, not preference (see
   "Choosing the language"). Push each case to the lowest layer that can hold it: a business
   rule belongs in a unit test, not in an E2E journey through a browser.
5. **Code.** Python — `python-test-automation`. TypeScript — `playwright-automation` (UI)
   and `api-testing` (REST/GraphQL).
6. **Verification.** A test must fail when the behavior it covers is broken. Confirm that
   explicitly: break the implementation (a status code, a response field) and check the test
   goes red. An unverified assertion is not a test.

## Choosing the language

| Signal in the target project | Test language |
|------------------------------|---------------|
| `pyproject.toml`, `conftest.py`, `requirements.txt` | Python |
| `package.json`, `tsconfig.json`, `playwright.config.ts` | TypeScript |
| Stated by the user or in `qa-project-context.md` | As stated |
| Python backend + JS frontend | API tests in Python, E2E in TypeScript |

Ask when there is no signal. Never mix two languages in the same test layer.

## Principles

1. **Test cases are separate from test code.** The coverage matrix and the oracles are a
   standalone artifact, reviewed before any code is written, and they survive a change of
   framework.
2. **Negative and boundary cases are mandatory.** The happy path is the least work and the
   least value; bugs live at boundaries, in authorization denials, and in malformed input.
3. **Contracts over spot-checks.** A Pydantic model (Python) or a Zod schema (TS) catches a
   changed type, a dropped field and an unexpected new one. `assert "id" in data` catches
   none of the three.
4. **No `sleep` / `waitForTimeout`.** Playwright auto-waits; background jobs get a poll with
   an explicit deadline.
5. **Isolation.** Every test passes standalone and under `-n auto` / `fullyParallel`. A
   difference between those two runs is shared state, not "flakiness".
6. **Never mute a flaky test.** `--reruns` and `retries` convert a reproducible bug into an
   intermittent one that nobody investigates again. Fix the isolation, the locator, or the
   product.
7. **Test code is production code.** Types, linting and review apply to it the same way.

## Boundaries

- The agent **does not change the product** to make a test pass. A red test on a real bug is
  the deliverable, not a problem: file the bug, keep the test.
- The agent does not run destructive tests against production. The environment check lives in
  a fixture, not in a comment.
- Secrets come from environment variables and CI secrets only — never from test code, and
  never into logs.

## Commands

> Fill in for the target project, for example:
> - Python: `uv sync --group test` · `pytest -n auto` · `ruff check tests/ && mypy tests/`
> - TypeScript: `npm ci` · `npx playwright test` · `npx playwright show-report`
