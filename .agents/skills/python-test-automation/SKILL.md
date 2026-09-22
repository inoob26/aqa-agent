---
name: python-test-automation
description: >-
  Write production-grade automated tests in Python: pytest fixtures and parametrization,
  E2E with pytest-playwright (sync and async), API tests with httpx, schema-as-contract
  validation with Pydantic v2, respx mocking, parallel execution with xdist, and CI
  reporting. The Python counterpart to playwright-automation and api-testing, which are
  TypeScript-first.
  Use when: the project under test is Python, the team asked for pytest, the repo has
  pyproject.toml / conftest.py / requirements.txt, or the user said "Python tests,"
  "pytest," "playwright-python," "httpx test."
  Not for: TypeScript suites — use playwright-automation (E2E) or api-testing (REST/GraphQL).
  Not for: choosing what to test — use test-planning, then ai-test-generation.
  Related: playwright-automation, api-testing, ai-test-generation, test-planning, qa-project-context.
license: MIT
metadata:
  author: initk.tech
  version: "1.0"
  category: automation
---

<objective>
The failure this prevents: an agent asked for Python tests transliterates TypeScript
Playwright idioms into Python — `time.sleep()` where auto-waiting belongs, bare
`assert response.json()["id"]` where a schema contract belongs, module-level clients that
leak sockets between tests. This skill encodes the pytest-native equivalents: fixtures over
setup methods, `expect()` over manual polling, Pydantic models over key spot-checks, and
function-scoped isolation that survives `-n auto`.
</objective>

## Discovery Questions

Check `.agents/qa-project-context.md` first — if it exists, use it and skip anything answered
there. Then ask only what's missing:

1. **Sync or async?** Sync (`pytest-playwright`, `httpx.Client`) is the default: simpler stack
   traces, no event-loop fixtures, fine for the vast majority of suites. Choose async only when
   the app under test is async *and* you need concurrent requests inside a single test, or when
   you're reusing the app's own `AsyncClient` setup. Mixing both in one suite is the mistake —
   pick one per test package.
2. **What layer?** E2E through a browser, API over HTTP, or in-process against an ASGI app.
   In-process (`httpx.ASGITransport`) is fastest and needs no running server, but it does not
   exercise your real middleware chain, TLS, or reverse proxy — use it for breadth, and keep a
   thin over-the-wire smoke suite for the things it cannot see.
3. **Where does the suite live?** `tests/` inside the app repo (unit + integration, runs on every
   PR) or a standalone QA repo (E2E against deployed environments). This changes dependency
   management and what "fast" means for the CI gate.
4. **Test data strategy?** Fixtures/factories per test, a seeded dataset, or production-like
   snapshots. Determines whether tests can run in parallel — shared mutable data forces serial
   execution, which is the single most common cause of a slow Python suite.

---

## Core Principles

1. **Fixtures, not setup methods.** `@pytest.fixture` composes, scopes, and tears down on
   failure. `setUp`/`tearDown` from unittest do none of that well. See
   `references/pytest-patterns.md`.
2. **Auto-waiting — never `time.sleep()`.** Playwright's Python API auto-waits exactly like the
   TS one. `expect(locator).to_be_visible()` retries until timeout. A sleep in a test is a
   locator or assertion problem wearing a disguise.
3. **Function scope by default.** Widen a fixture's scope (`module`, `session`) only when setup
   is genuinely expensive *and* the fixture is read-only. A mutable session-scoped fixture makes
   tests order-dependent, and the failure only shows up under `-n auto` or `-p randomly`.
4. **Assert on contracts, not on keys.** `UserResponse.model_validate(response.json())` fails when
   the API drops a field, changes a type, or adds an unexpected one. `assert "id" in data` passes
   through all three.
5. **One reason to fail per test.** A test named `test_checkout` that asserts on the cart, the
   payment call, and the confirmation email tells you nothing when it goes red. Parametrize or
   split.
6. **Every test must pass alone and in parallel.** `pytest tests/test_x.py::test_y` and
   `pytest -n auto` must both work. If they don't, the suite has shared state, not a flakiness
   problem.

> **Calibrate to team maturity** (`team_maturity` in `.agents/qa-project-context.md`):
> - **startup** — `pytest` + `httpx`, 5–10 critical-path tests, one CI job, no parallelism yet.
> - **growing** — add `pytest-playwright` for E2E, `pytest-xdist` for parallelism, markers to
>   split fast/slow, coverage on the unit layer.
> - **established** — Pydantic contracts on every endpoint, `respx` for third-party boundaries,
>   tracing on failure, Allure reporting, flakiness tracking in CI.

---

## Project Structure

```
project-root/
├── pyproject.toml              # deps + [tool.pytest.ini_options]
├── tests/
│   ├── conftest.py             # session config, base_url, shared clients
│   ├── unit/
│   │   └── test_pricing.py
│   ├── api/
│   │   ├── conftest.py         # api_client, auth fixtures
│   │   ├── schemas.py          # Pydantic response contracts
│   │   └── test_users.py
│   ├── e2e/
│   │   ├── conftest.py         # browser context args, storage state
│   │   ├── pages/              # page objects
│   │   │   ├── base_page.py
│   │   │   └── login_page.py
│   │   └── test_login.py
│   └── factories.py            # test data builders
└── .agents/qa-project-context.md
```

Rules that keep this structure honest:

- **`conftest.py` per layer, not one giant root file.** A fixture belongs in the lowest
  `conftest.py` that all its users share. Root `conftest.py` holds only what every layer needs.
- **Page objects expose intent, not elements.** `login_page.sign_in(user)` — not
  `login_page.email_input`. A test that reaches for a locator through a page object has defeated
  the abstraction.
- **Schemas live next to the tests that assert them**, and are generated from the OpenAPI spec
  when one exists (`datamodel-code-generator`) rather than hand-written.

---

## Baseline Configuration

```toml
# pyproject.toml
[dependency-groups]
test = [
    "pytest>=8.3",
    "pytest-playwright>=0.7",     # sync; use pytest-playwright-asyncio for async
    "pytest-xdist>=3.6",          # parallel execution
    "httpx>=0.28",
    "pydantic>=2.9",
    "respx>=0.22",                # httpx mocking
    "polyfactory>=2.18",          # test data factories
]

[tool.pytest.ini_options]
testpaths = ["tests"]
# --strict-markers: a typo'd marker fails the run instead of silently selecting nothing.
# -ra: show the reason for every non-passing test at the end.
addopts = "-ra --strict-markers --strict-config"
markers = [
    "smoke: critical path, must pass before anything else runs",
    "slow: takes >5s, excluded from the fast PR gate",
    "e2e: drives a real browser against a deployed environment",
]
```

Run configurations worth wiring into CI:

```bash
pytest -m smoke                  # fast gate, blocks the merge
pytest -n auto -m "not slow"     # full parallel run on PR
pytest --tracing=retain-on-failure --video=retain-on-failure   # E2E debugging artifacts
```

---

## E2E: pytest-playwright

The `page` fixture is function-scoped and gives each test a fresh `BrowserContext` — isolation
comes for free, so never reuse a page across tests.

```python
import re
from playwright.sync_api import Page, expect

from tests.e2e.pages.login_page import LoginPage


def test_valid_credentials_land_on_dashboard(page: Page) -> None:
    login = LoginPage(page)
    login.goto()
    login.sign_in("user@example.com", "correct-horse")

    # Web-first assertion: retries until the timeout, no explicit wait needed.
    expect(page).to_have_url(re.compile(r"/dashboard$"))
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def test_wrong_password_shows_error_and_stays_put(page: Page) -> None:
    login = LoginPage(page)
    login.goto()
    login.sign_in("user@example.com", "wrong")

    expect(login.error_banner).to_have_text("Invalid email or password")
    expect(page).to_have_url(re.compile(r"/login$"))
```

A page object in Python — locators are lazy, so build them in `__init__` and resolve them at use:

```python
from playwright.sync_api import Locator, Page


class LoginPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        # Locators are declarative descriptions; nothing touches the DOM until an action.
        self.email = page.get_by_label("Email")
        self.password = page.get_by_label("Password")
        self.submit = page.get_by_role("button", name="Sign in")
        self.error_banner = page.get_by_role("alert")

    def goto(self) -> None:
        self.page.goto("/login")

    def sign_in(self, email: str, password: str) -> None:
        self.email.fill(email)
        self.password.fill(password)
        self.submit.click()
```

Locator priority is the same as in `playwright-automation`: `get_by_role` > `get_by_label` >
`get_by_test_id` > CSS as a last resort. For selector strategy, storage-state auth, network
mocking and trace triage, that skill's reference files apply verbatim — only the syntax changes.
Python-specific fixtures, async variants and CLI options are in
`references/playwright-python.md`.

---

## API: httpx + Pydantic contracts

One client fixture, one schema per response shape:

```python
# tests/api/conftest.py
from collections.abc import Iterator

import httpx
import pytest


@pytest.fixture(scope="session")
def api_client(base_url: str) -> Iterator[httpx.Client]:
    # Session-scoped and read-only: connection pooling is the whole point, and the
    # client carries no per-test state. Timeout is explicit — httpx defaults to 5s,
    # which silently turns a slow endpoint into a confusing connect error.
    with httpx.Client(
        base_url=base_url,
        timeout=httpx.Timeout(10.0, connect=5.0),
        follow_redirects=False,      # redirects are behavior worth asserting on
    ) as client:
        yield client


@pytest.fixture
def authed_client(api_client: httpx.Client, test_user: User) -> Iterator[httpx.Client]:
    # Function-scoped: a token is per-test state. Restore headers so the shared
    # session client never leaks credentials into an unauthenticated test.
    token = login(api_client, test_user)
    api_client.headers["Authorization"] = f"Bearer {token}"
    yield api_client
    del api_client.headers["Authorization"]
```

```python
# tests/api/schemas.py
from datetime import datetime
from pydantic import BaseModel, ConfigDict, EmailStr


class UserResponse(BaseModel):
    # extra="forbid" turns an unexpected new field into a failing test — that is the
    # point of a contract test. Drop to the default only for endpoints you don't own.
    model_config = ConfigDict(extra="forbid")

    id: int
    email: EmailStr
    display_name: str
    created_at: datetime
```

```python
# tests/api/test_users.py
import httpx
import pytest

from tests.api.schemas import UserResponse

HTTP_CREATED = 201
HTTP_UNPROCESSABLE = 422
MAX_RESPONSE_MS = 500


def test_create_user_returns_contract_shaped_body(authed_client: httpx.Client) -> None:
    response = authed_client.post("/users", json={"email": "a@b.com", "display_name": "A"})

    assert response.status_code == HTTP_CREATED
    # Validation is the assertion: wrong type, missing field or extra field all fail here.
    user = UserResponse.model_validate(response.json())
    assert user.email == "a@b.com"
    assert response.elapsed.total_seconds() * 1000 < MAX_RESPONSE_MS


@pytest.mark.parametrize(
    ("payload", "invalid_field"),
    [
        ({"email": "not-an-email", "display_name": "A"}, "email"),
        ({"email": "a@b.com", "display_name": ""}, "display_name"),
        ({"display_name": "A"}, "email"),
    ],
    ids=["malformed-email", "empty-name", "missing-email"],
)
def test_invalid_payload_is_rejected_with_field_detail(
    authed_client: httpx.Client, payload: dict[str, str], invalid_field: str
) -> None:
    response = authed_client.post("/users", json=payload)

    assert response.status_code == HTTP_UNPROCESSABLE
    # Assert the error names the offending field — a bare 422 check passes even when
    # the API blames the wrong field.
    assert invalid_field in response.text
```

Auth boundaries, pagination, CRUD lifecycles, GraphQL, `respx` mocking and in-process
`ASGITransport` testing are in `references/api-httpx.md`. For the conceptual layer — what to
assert, why contracts beat spot-checks — `api-testing` applies unchanged; this skill supplies the
Python syntax.

---

## Do Not

These are the Python-specific failure modes. Each one produces a suite that passes on the author's
machine and flakes in CI.

| Never | Instead | Why |
|-------|---------|-----|
| `time.sleep(2)` | `expect(locator).to_be_visible()` | Sleeps are either too short (flake) or too long (slow). Playwright already retries. |
| `page.wait_for_timeout(1000)` | A web-first assertion on the thing you're waiting for | Same failure, Playwright-flavored. |
| `assert "id" in response.json()` | `Model.model_validate(response.json())` | Spot-checks pass through type changes, dropped siblings and new fields. |
| Module-level `httpx.Client()` | A fixture that `yield`s inside `with` | Module-level clients never close; sockets leak and `-n auto` multiplies the leak. |
| `except Exception` in a test helper | Let it raise, or catch the specific type | A swallowed exception turns a real bug into a green test. |
| Mutable `scope="session"` fixtures | Function scope, or `scope="session"` + a per-test copy | The first test to mutate it decides the outcome of every test after it. |
| `assert response.status_code == 200` alone | Status **and** body contract **and** headers | A 200 with an empty body is still a broken endpoint. |
| `--reruns 3` to hide a flaky test | Fix the isolation or the locator | Reruns convert a reproducible bug into an intermittent one you stop looking at. |
| `time.sleep()` to wait for an async job | Poll a status endpoint with an explicit deadline, or assert on the queue | See `references/api-httpx.md` for the polling helper. |
| `unittest.TestCase` + pytest fixtures | Plain functions + fixtures | Fixtures cannot be injected into `TestCase` methods; you lose parametrization too. |

---

## Workflow

1. **Read the context.** `.agents/qa-project-context.md` for stack, conventions and risk areas.
   Missing? Offer to create it via `qa-project-context` before writing tests.
2. **Get the test cases first.** For a task description or PRD, run `ai-test-generation`'s
   pipeline (requirements → risk → coverage matrix → scenarios → oracles) and only then write
   code. For sprint/release scope, `test-planning`. Writing test code before the coverage matrix
   exists is how suites end up with forty happy-path tests and no negative cases.
3. **Pick the layer.** Push each case as low as it will go: a pricing rule belongs in a unit test,
   not an E2E checkout. Reserve E2E for journeys that genuinely cross the whole stack.
4. **Write the failing test first** where possible — a test that has never failed has never been
   verified to test anything.
5. **Verify isolation.** Run the new test alone, then the file, then `pytest -n auto`. Three
   different results means shared state.
6. **Check the assertions are real.** Break the implementation on purpose (change a status code,
   drop a field) and confirm the test goes red. Skip this and you ship assertions that cannot fail.

---

## Verification Checklist

Before handing the suite back:

```bash
pytest --collect-only -q          # no import errors, expected test count
pytest -n auto                    # passes in parallel
pytest -p no:randomly --lf        # last failures reproduce deterministically
ruff check tests/ && mypy tests/  # the suite is production code too
```

- [ ] No `time.sleep`, `wait_for_timeout`, or `--reruns` anywhere in the suite.
- [ ] Every API response asserted through a Pydantic model, not key membership.
- [ ] Every test passes standalone and under `-n auto`.
- [ ] Every fixture that holds a client, file, or connection uses `yield` inside a
      context manager.
- [ ] Negative and boundary cases present, not only happy paths.
- [ ] Test names state the behavior and the expectation
      (`test_expired_token_is_rejected_with_401`), not the function under test
      (`test_login_2`).
- [ ] At least one test was confirmed to fail when the behavior it covers is broken.

---

## References

| File | Read when |
|------|-----------|
| `references/pytest-patterns.md` | Fixture scoping and composition, parametrization, markers, factories, conftest layout, mocking |
| `references/playwright-python.md` | Browser fixtures and CLI options, sync vs async, auth via storage state, network interception, tracing |
| `references/api-httpx.md` | Client fixtures, auth flows, CRUD lifecycles, pagination, GraphQL, respx, ASGI in-process testing, async polling |
| `references/ci-and-reporting.md` | GitHub Actions/GitLab jobs, parallelism and sharding, artifacts, Allure, coverage, flakiness tracking |
