# CI and Reporting

Getting a Python suite to run fast, fail informatively, and leave behind artifacts someone can
act on.

## Tiered Pipeline

Not every test runs on every push. Three tiers, three triggers:

| Tier | Selection | Trigger | Budget |
|------|-----------|---------|--------|
| Fast gate | `-m "not slow and not e2e"` | Every push | < 3 min |
| Full PR run | `-n auto -m "not slow"` | PR open/update | < 10 min |
| Nightly | everything, all browsers | Schedule | Unbounded |

If the fast gate exceeds its budget, move tests down a layer — don't raise the budget.

---

## GitHub Actions

```yaml
name: tests

on:
  push:
    branches: [main]
  pull_request:

concurrency:
  # A new push supersedes the previous run on the same branch.
  group: tests-${{ github.ref }}
  cancel-in-progress: true

jobs:
  unit-api:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --group test
      - name: Run unit and API tests
        run: uv run pytest -n auto -m "not e2e" --junitxml=junit.xml
        env:
          QA_USER: ${{ secrets.QA_USER }}
          QA_PASSWORD: ${{ secrets.QA_PASSWORD }}
      - uses: actions/upload-artifact@v4
        if: always()          # the report matters most when the job failed
        with:
          name: junit-unit-api
          path: junit.xml

  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    strategy:
      fail-fast: false        # one browser failing must not hide the others
      matrix:
        browser: [chromium, firefox]
        shard: [1, 2, 3, 4]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true
      - run: uv sync --group test
      - name: Install browsers
        run: uv run playwright install --with-deps ${{ matrix.browser }}
      - name: Run E2E shard
        run: |
          uv run pytest -m e2e \
            --browser ${{ matrix.browser }} \
            --splits 4 --group ${{ matrix.shard }} \
            --tracing retain-on-failure \
            --video retain-on-failure \
            --junitxml=junit-${{ matrix.browser }}-${{ matrix.shard }}.xml
        env:
          PYTEST_BASE_URL: ${{ vars.STAGING_URL }}
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: traces-${{ matrix.browser }}-${{ matrix.shard }}
          path: test-results/
          retention-days: 7
```

Sharding across machines needs `pytest-split` (`--splits N --group M`); `pytest-xdist` (`-n auto`)
parallelizes within one machine. They compose: shard across runners, `-n auto` inside each.

`pytest-split` distributes by recorded duration — generate the durations file periodically
(`pytest --store-durations`) and commit it, or shards drift out of balance.

---

## GitLab CI

```yaml
stages: [test]

variables:
  UV_CACHE_DIR: .uv-cache

.python-job:
  image: python:3.12-slim
  cache:
    key: uv-$CI_COMMIT_REF_SLUG
    paths: [.uv-cache]
  before_script:
    - pip install uv && uv sync --group test

unit-api:
  extends: .python-job
  stage: test
  script:
    - uv run pytest -n auto -m "not e2e" --junitxml=junit.xml
  artifacts:
    when: always
    reports:
      junit: junit.xml

e2e:
  extends: .python-job
  stage: test
  image: mcr.microsoft.com/playwright/python:v1.49.0-noble
  parallel: 4
  script:
    - uv run pytest -m e2e --splits 4 --group $CI_NODE_INDEX
        --tracing retain-on-failure --junitxml=junit-e2e-$CI_NODE_INDEX.xml
  artifacts:
    when: on_failure
    paths: [test-results/]
    expire_in: 1 week
    reports:
      junit: junit-e2e-*.xml
```

The official Playwright Python image ships the browsers and system dependencies — use it for E2E
jobs instead of installing them on every run.

---

## Artifacts That Make a Failure Debuggable

A red CI job with only a stack trace costs an hour. These cost seconds:

| Artifact | Produced by | Read it with |
|----------|-------------|--------------|
| Trace (DOM, network, console, timeline) | `--tracing retain-on-failure` | `playwright show-trace trace.zip` |
| Video | `--video retain-on-failure` | Any player |
| Screenshot | `--screenshot only-on-failure` | — |
| JUnit XML | `--junitxml=junit.xml` | CI's native test report UI |
| HTML report | `pytest-html`: `--html=report.html --self-contained-html` | Browser |

Always upload with `if: always()` or `when: on_failure` — a conditional that skips upload on
failure is the most common way teams end up with no evidence.

---

## Allure

Richer than JUnit when you need history, flakiness trends, and step-level detail:

```bash
uv add --group test allure-pytest
uv run pytest --alluredir=allure-results
allure serve allure-results
```

```python
import allure


@allure.feature("Checkout")
@allure.story("Payment failure")
@allure.severity(allure.severity_level.CRITICAL)
@allure.issue("PROJ-1234")
def test_declined_card_shows_retry_prompt(page: Page) -> None:
    with allure.step("Fill the cart"):
        ...
    with allure.step("Submit a card that the PSP declines"):
        ...
    allure.attach(
        page.screenshot(), name="decline-banner", attachment_type=allure.attachment_type.PNG
    )
```

Steps are worth the annotation only on long E2E journeys. On a three-line API test they are noise
— the test name already says everything.

---

## Coverage

Coverage belongs on the unit and integration layers, inside the app repo. Measuring coverage from
an E2E suite against a deployed environment measures almost nothing useful.

```toml
[tool.coverage.run]
branch = true
source = ["src"]
omit = ["*/migrations/*", "*/__main__.py"]

[tool.coverage.report]
show_missing = true
skip_covered = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

```bash
pytest --cov --cov-report=term-missing --cov-report=xml
```

Use the report to find untested branches, not to hit a number. A suite tuned to a coverage
threshold grows tests that execute code without asserting on it — which is worse than no test,
because it looks like protection.

---

## Flakiness

**Do not paper over it.** `pytest-rerunfailures` (`--reruns 3`) converts a reproducible bug into
an intermittent one that nobody investigates again.

Find it instead:

```bash
pytest --count 20 tests/e2e/test_checkout.py     # pytest-repeat: does it fail sometimes?
pytest -p randomly                               # pytest-randomly: order dependence?
pytest -n auto                                   # isolation under parallelism?
pytest tests/e2e/test_checkout.py::test_x        # passes alone but fails in the suite = shared state
```

The three causes, in order of frequency:

1. **Shared mutable state** — a session-scoped fixture, a fixed username, a database row two tests
   both touch. Fix: function scope and unique data.
2. **A race the test doesn't wait for** — a `sleep`, or an assertion that reads state once. Fix: a
   web-first assertion or an explicit poll with a deadline.
3. **A genuinely flaky application** — a real race condition in the product. Fix: file the bug.
   This is the test doing its job.

Track quarantined tests explicitly rather than deleting or rerunning them:

```python
@pytest.mark.xfail(reason="PROJ-5678: race in the order queue, under investigation", strict=False)
def test_concurrent_orders_do_not_oversell(...): ...
```

A quarantine with a ticket number and a date is a debt you can pay. `--reruns 3` is a debt you
can't even see.

---

## Environment and Secrets

```python
# tests/conftest.py
import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def require_credentials() -> None:
    # Fail fast with a readable message instead of a 401 in every test.
    missing = [var for var in ("QA_USER", "QA_PASSWORD") if not os.getenv(var)]
    if missing:
        pytest.exit(f"Missing required environment variables: {', '.join(missing)}", returncode=1)
```

Rules that hold everywhere:

- Credentials come from CI secrets or a local `.env` that is gitignored — never from the repo.
- Never log a token, even at debug level; httpx event hooks that dump headers will do it for you
  by accident.
- Tests that mutate data must not be runnable against production. Enforce it in a fixture, not in
  a comment:

```python
@pytest.fixture(autouse=True)
def block_destructive_tests_on_prod(request: pytest.FixtureRequest) -> None:
    if request.config.getoption("--env") == "prod" and "destructive" in request.keywords:
        pytest.skip("Destructive tests never run against production")
```
