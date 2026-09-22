# Playwright for Python

The Python bindings expose the same engine as the TypeScript API — auto-waiting, web-first
assertions, locators, tracing. What differs is the fixture layer (`pytest-playwright` instead of
`@playwright/test`), the sync/async split, and how configuration is supplied (CLI options and
fixture overrides instead of `playwright.config.ts`).

For **strategy** — locator priority, page object design, what to mock, how to read a trace — the
`playwright-automation` skill's reference files apply unchanged. This file covers the Python
mechanics.

## Installation

```bash
uv add --group test pytest-playwright     # sync API (default choice)
playwright install --with-deps chromium   # browsers are a separate download
```

Async suites use a different plugin — they are mutually exclusive in one test package:

```bash
uv add --group test pytest-playwright-asyncio
```

---

## Built-in Fixtures

`pytest-playwright` provides these. All browser-level fixtures are function-scoped, so isolation
is the default.

| Fixture | Scope | What it is |
|---------|-------|------------|
| `page` | function | A `Page` in a fresh `BrowserContext` — the one you want 95% of the time |
| `context` | function | The `BrowserContext` behind `page`; request it to open a second page |
| `browser` | session | The launched browser; rarely needed directly |
| `browser_name` | session | `"chromium"` / `"firefox"` / `"webkit"` — useful for conditional skips |
| `playwright` | session | The Playwright object, for `selectors`, `devices`, `request` |
| `new_context` | function | A factory for extra contexts (multi-user tests) |

```python
def test_two_users_see_each_others_messages(new_context, base_url: str) -> None:
    # Two independent contexts = two independent sessions, no cookie bleed.
    alice = new_context().new_page()
    bob = new_context().new_page()
    ...
```

---

## Configuration

There is no `playwright.config.ts`. Configuration comes from three places:

### 1. CLI options (per run)

```bash
pytest --browser firefox --browser webkit    # repeatable; runs the suite per browser
pytest --headed --slowmo 500                 # watch it happen
pytest --base-url https://staging.example.com
pytest --tracing retain-on-failure           # on / off / retain-on-failure
pytest --video retain-on-failure
pytest --screenshot only-on-failure
pytest --device "iPhone 15"                  # a Playwright device descriptor
pytest --output test-results/                # where artifacts land
```

### 2. `addopts` (per project)

```toml
[tool.pytest.ini_options]
addopts = """
-ra --strict-markers
--base-url=http://localhost:3000
--tracing=retain-on-failure
--screenshot=only-on-failure
--output=test-results
"""
```

### 3. Fixture overrides (per suite or per file)

Override the plugin's own fixtures in `conftest.py` — this is the Python equivalent of a
`projects` entry or a `use` block.

```python
# tests/e2e/conftest.py
import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict) -> dict:
    return {**browser_type_launch_args, "args": ["--disable-dev-shm-usage"]}


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict, base_url: str) -> dict:
    return {
        **browser_context_args,
        "base_url": base_url,
        "locale": "en-GB",
        "timezone_id": "Europe/Prague",
        "viewport": {"width": 1440, "height": 900},
        # Deterministic rendering for anything screenshot-adjacent.
        "reduced_motion": "reduce",
    }
```

Custom test-id attribute (when the app doesn't use `data-testid`):

```python
@pytest.fixture(scope="session", autouse=True)
def configure_test_id(playwright) -> None:
    playwright.selectors.set_test_id_attribute("data-qa")
```

Global timeouts — note these are per-context and per-assertion, set separately:

```python
from playwright.sync_api import expect

expect.set_options(timeout=10_000)     # web-first assertion timeout, default 5s


@pytest.fixture(autouse=True)
def slow_app_timeout(page: Page) -> None:
    page.set_default_timeout(15_000)          # actions
    page.set_default_navigation_timeout(30_000)
```

---

## Locators and Assertions

Identical priority to the TypeScript skill: `get_by_role` > `get_by_label` > `get_by_placeholder`
> `get_by_text` > `get_by_test_id` > CSS/XPath as a last resort.

```python
from playwright.sync_api import expect

page.get_by_role("button", name="Add to cart").click()
page.get_by_label("Quantity").fill("3")
page.get_by_test_id("cart-badge")

# Chaining and filtering — the Python names are snake_case.
row = page.get_by_role("row").filter(has_text="Wireless Mouse")
row.get_by_role("button", name="Remove").click()

# Web-first assertions retry until timeout. These are the only assertions that
# should touch the DOM — a bare `assert locator.is_visible()` reads the state once
# and races the app.
expect(page.get_by_role("alert")).to_have_text("Removed from cart")
expect(page.get_by_test_id("cart-badge")).to_have_text("0")
expect(page.get_by_role("button", name="Checkout")).to_be_disabled()
expect(page).to_have_url(re.compile(r"/cart$"))
expect(page.get_by_role("listitem")).to_have_count(2)
```

Negative assertions use `not_`:

```python
expect(page.get_by_text("Loading")).not_to_be_visible()
```

---

## Authentication via Storage State

Log in once per session, reuse the cookies everywhere. This is the single biggest speedup in an
E2E suite.

```python
# tests/e2e/conftest.py
from pathlib import Path

import pytest
from playwright.sync_api import Browser


@pytest.fixture(scope="session")
def storage_state_path(tmp_path_factory: pytest.TempPathFactory, browser: Browser,
                       base_url: str) -> Path:
    state = tmp_path_factory.mktemp("auth") / "state.json"
    page = browser.new_page(base_url=base_url)
    page.goto("/login")
    page.get_by_label("Email").fill(os.environ["E2E_USER"])
    page.get_by_label("Password").fill(os.environ["E2E_PASSWORD"])
    page.get_by_role("button", name="Sign in").click()
    # Wait for the state that proves login finished before saving cookies.
    page.wait_for_url("**/dashboard")
    page.context.storage_state(path=state)
    page.close()
    return state


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict, storage_state_path: Path) -> dict:
    return {**browser_context_args, "storage_state": str(storage_state_path)}
```

Tests that must be anonymous opt out by building their own context:

```python
def test_dashboard_redirects_anonymous_users(new_context, base_url: str) -> None:
    page = new_context(storage_state=None).new_page()
    page.goto(f"{base_url}/dashboard")
    expect(page).to_have_url(re.compile(r"/login"))
```

For multiple roles, produce one state file per role and parametrize the fixture.

---

## Network Interception

```python
def test_empty_state_when_api_returns_no_orders(page: Page) -> None:
    # Route before navigation, or the first request escapes the handler.
    page.route(
        "**/api/orders*",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"items": [], "total": 0}),
        ),
    )
    page.goto("/orders")
    expect(page.get_by_text("No orders yet")).to_be_visible()


def test_checkout_surfaces_payment_failure(page: Page) -> None:
    page.route("**/api/payments", lambda route: route.fulfill(status=502))
    ...


def test_order_request_carries_idempotency_key(page: Page) -> None:
    # Assert on an outgoing request without mocking the response.
    with page.expect_request("**/api/orders") as request_info:
        page.get_by_role("button", name="Place order").click()
    assert request_info.value.headers.get("idempotency-key")
```

Block third parties that slow the suite and add nothing:

```python
@pytest.fixture(autouse=True)
def block_analytics(page: Page) -> None:
    page.route(re.compile(r"(google-analytics|hotjar|segment)\.com"), lambda r: r.abort())
```

---

## Sync vs Async

**Sync is the default.** Choose async only when the test itself needs concurrency, or the
surrounding codebase is async and reusing its helpers matters.

```python
# Sync — pytest-playwright
from playwright.sync_api import Page, expect

def test_login(page: Page) -> None:
    page.goto("/login")
    expect(page.get_by_role("heading")).to_have_text("Sign in")
```

```python
# Async — pytest-playwright-asyncio
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_login(page: Page) -> None:
    await page.goto("/login")
    await expect(page.get_by_role("heading")).to_have_text("Sign in")
```

Every action and assertion is awaited in the async API, including `expect`. Forgetting one `await`
produces a test that passes instantly and asserts nothing — the most dangerous failure mode in the
async variant, and the main reason to prefer sync.

With `pytest-asyncio`, set `asyncio_mode = "auto"` in `pyproject.toml` to drop the per-test
marker.

---

## Parallel Execution

`pytest-xdist` distributes across processes; each worker launches its own browser.

```bash
pytest -n auto                   # one worker per CPU
pytest -n 4 --dist loadfile      # keep a file's tests on one worker
```

Requirements for this to work: no shared mutable fixtures, unique test data per test, and no
reliance on a fixed port. A suite that needs `-p no:randomly` or a fixed worker count has an
isolation bug.

For CI sharding across machines, see `ci-and-reporting.md`.

---

## Debugging

```bash
PWDEBUG=1 pytest tests/e2e/test_login.py::test_valid   # Playwright Inspector, step through
pytest --headed --slowmo 1000                          # watch at human speed
pytest --tracing on                                    # always record
playwright show-trace test-results/.../trace.zip       # DOM snapshots + network + console
playwright codegen https://staging.example.com         # generate locators, then rewrite them
```

`codegen` output is a starting point, never a deliverable: it emits CSS and `nth` selectors that
break on the next refactor. Take the flow, replace the locators.

To capture console errors as part of a test:

```python
@pytest.fixture(autouse=True)
def fail_on_console_errors(page: Page) -> Iterator[None]:
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    yield
    assert not errors, f"Console errors during test: {errors}"
```

Introduce this one deliberately — on an app with pre-existing console noise it fails everything at
once. Fix the noise or scope the fixture to new tests.

---

## API Requests from Playwright

Playwright's `request` fixture is useful for E2E *setup* — create the entity over HTTP, then
assert on it in the UI. For API testing proper, use `httpx` (see `api-httpx.md`); it has better
error messages and does not need a browser.

```python
def test_existing_order_appears_in_list(page: Page, playwright, base_url: str) -> None:
    api = playwright.request.new_context(base_url=base_url)
    order = api.post("/api/orders", data={"sku": "ABC-1"}).json()

    page.goto("/orders")
    expect(page.get_by_test_id(f"order-{order['id']}")).to_be_visible()
    api.dispose()
```
