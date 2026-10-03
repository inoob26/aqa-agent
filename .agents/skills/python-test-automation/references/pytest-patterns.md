# pytest Patterns

Fixture design, parametrization, markers and test data — the parts of pytest that decide whether
a suite stays maintainable at 500 tests.

## Fixture Scoping

Scope is a tradeoff between speed and isolation. Get it wrong in the expensive direction and the
suite is slow; wrong in the cheap direction and it is flaky.

| Scope | Created | Use for |
|-------|---------|---------|
| `function` (default) | Per test | Anything mutable: test users, request payloads, page objects |
| `class` | Per test class | Shared read-only setup for a related group |
| `module` | Per file | An expensive read-only resource used by one file |
| `package` | Per directory | A layer-wide resource (a seeded schema for `tests/api/`) |
| `session` | Once per run | Connection pools, browser launch, config, read-only reference data |

The rule: **widen the scope only when the fixture is read-only.** A session-scoped fixture that
any test mutates makes every later test depend on execution order, and that dependency only
surfaces under `-n auto` or `pytest-randomly`.

```python
import pytest

# Correct: read-only config, built once.
@pytest.fixture(scope="session")
def api_config() -> ApiConfig:
    return ApiConfig.from_env()


# Correct: mutable per-test state, rebuilt every time.
@pytest.fixture
def draft_order(authed_client: httpx.Client) -> Iterator[Order]:
    order = create_order(authed_client)
    yield order
    delete_order(authed_client, order.id)      # runs even if the test fails
```

### Teardown belongs after `yield`

Code after `yield` runs even when the test fails, which is exactly when cleanup matters most.
`request.addfinalizer` does the same job and is only worth it when you register cleanups
conditionally.

```python
@pytest.fixture
def temp_workspace(tmp_path: Path) -> Iterator[Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    yield workspace
    # Nothing needed here — tmp_path is cleaned by pytest. Prefer built-in fixtures
    # (tmp_path, monkeypatch, caplog, capsys) over hand-rolled equivalents.
```

### Composition over inheritance

Fixtures request other fixtures. This is how you build a graph instead of a base-class hierarchy.

```python
@pytest.fixture
def test_user(api_client: httpx.Client) -> Iterator[User]:
    user = create_user(api_client)
    yield user
    delete_user(api_client, user.id)


@pytest.fixture
def authed_client(api_client: httpx.Client, test_user: User) -> Iterator[httpx.Client]:
    ...


@pytest.fixture
def user_with_orders(authed_client: httpx.Client, test_user: User) -> User:
    for _ in range(3):
        create_order(authed_client, test_user.id)
    return test_user
```

### `conftest.py` placement

A fixture goes in the **lowest** `conftest.py` shared by all its users. Root `conftest.py` is for
what every layer needs — usually `base_url`, environment config, and the CLI options that select
an environment.

```python
# tests/conftest.py — the whole suite
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--env",
        default="staging",
        choices=["local", "staging", "prod"],
        help="Target environment for API and E2E tests",
    )


@pytest.fixture(scope="session")
def base_url(request: pytest.FixtureRequest) -> str:
    return {
        "local": "http://localhost:8000",
        "staging": "https://staging.example.com",
        "prod": "https://example.com",
    }[request.config.getoption("--env")]
```

### `autouse` — use sparingly

An `autouse` fixture runs for every test in its scope, whether or not the test needs it. That is
right for resetting global state and wrong for anything a reader would need to know about.

```python
# Justified: without this, a test that changes the locale leaks into the next one.
@pytest.fixture(autouse=True)
def reset_locale() -> Iterator[None]:
    original = locale.getlocale()
    yield
    locale.setlocale(locale.LC_ALL, original)
```

If an `autouse` fixture is what makes a test pass, the test is lying about its preconditions —
request the fixture explicitly instead.

---

## Parametrization

One test function, many cases. Each case reports as a separate test, so a failure names the exact
input.

```python
MIN_PASSWORD_LENGTH = 8

@pytest.mark.parametrize(
    ("password", "is_accepted"),
    [
        ("Str0ng!Pass", True),
        ("short1!", False),                  # below MIN_PASSWORD_LENGTH
        ("alllowercase1!", False),           # no uppercase
        ("NoDigitsHere!", False),            # no digit
        ("", False),                         # boundary: empty
    ],
    ids=["valid", "too-short", "no-uppercase", "no-digit", "empty"],
)
def test_password_policy(password: str, is_accepted: bool) -> None:
    assert is_valid_password(password) is is_accepted
```

**Always pass `ids`** when the parameters aren't self-describing. Without them pytest generates
`test_password_policy[Str0ng!Pass-True]`, which is unreadable in a CI report and unusable as a
`-k` filter.

### Stacked parametrize is a cartesian product

```python
# 3 browsers x 2 roles = 6 tests. Deliberate here; an accident at 5 x 5 x 4.
@pytest.mark.parametrize("role", ["admin", "viewer"])
@pytest.mark.parametrize("browser_name", ["chromium", "firefox", "webkit"])
def test_dashboard_access(role: str, browser_name: str) -> None: ...
```

### Parametrizing a fixture

When the *setup* varies rather than the input, parametrize the fixture — every test that requests
it runs once per parameter.

```python
@pytest.fixture(params=["free", "pro", "enterprise"])
def subscription_tier(request: pytest.FixtureRequest) -> str:
    return request.param


# Runs three times, once per tier, with no change to the test body.
def test_feature_gate_matches_tier(subscription_tier: str) -> None: ...
```

### `pytest.param` for per-case marks

```python
@pytest.mark.parametrize(
    "endpoint",
    [
        "/users",
        "/orders",
        pytest.param("/reports", marks=pytest.mark.slow),
        pytest.param(
            "/legacy",
            marks=pytest.mark.xfail(reason="PROJ-1234: removed in v3, still routed", strict=True),
        ),
    ],
)
def test_endpoint_responds(api_client: httpx.Client, endpoint: str) -> None: ...
```

`strict=True` on `xfail` matters: without it, a test that starts passing stays green and you never
learn the bug was fixed.

---

## Markers

Markers are how CI splits the suite. Declare every one in `pyproject.toml` and run with
`--strict-markers` so a typo fails loudly.

```python
@pytest.mark.smoke
def test_homepage_loads(page: Page) -> None: ...


@pytest.mark.slow
@pytest.mark.e2e
def test_full_checkout_journey(page: Page) -> None: ...


# Skip conditionally — never comment a test out. A commented test is invisible;
# a skipped one is reported with its reason.
@pytest.mark.skipif(
    os.getenv("ENV") == "prod",
    reason="Creates real orders; staging and local only",
)
def test_order_creation(authed_client: httpx.Client) -> None: ...
```

```bash
pytest -m smoke                    # PR gate
pytest -m "not slow and not e2e"   # fast feedback
pytest -m "e2e and not slow"       # boolean expressions work
```

---

## Test Data

### Factories over fixtures for variation

A fixture gives one object. A factory gives any object, which is what parametrized and
multi-entity tests need.

```python
# Factory-as-fixture: the test controls the shape, the fixture controls cleanup.
@pytest.fixture
def make_user(api_client: httpx.Client) -> Iterator[Callable[..., User]]:
    created: list[int] = []

    def _make(*, email: str | None = None, role: str = "viewer") -> User:
        user = create_user(api_client, email=email or f"{uuid4().hex}@example.com", role=role)
        created.append(user.id)
        return user

    yield _make

    for user_id in created:
        delete_user(api_client, user_id)


def test_admin_sees_all_orders(make_user: Callable[..., User]) -> None:
    admin = make_user(role="admin")
    viewer = make_user(role="viewer")
    ...
```

### Unique data, always

Hardcoded emails and usernames collide the moment two tests run in parallel, or the moment a
cleanup fails. Generate them.

```python
from uuid import uuid4

email = f"test-{uuid4().hex[:12]}@example.com"
```

### polyfactory for Pydantic models

When the schema already exists, generate instances from it rather than hand-writing dicts:

```python
from polyfactory.factories.pydantic_factory import ModelFactory


class UserFactory(ModelFactory[UserCreate]):
    __model__ = UserCreate

    # Override only the fields the test cares about; the rest are generated.
    role = "viewer"


payload = UserFactory.build(email="specific@example.com").model_dump()
```

---

## Mocking

Default to not mocking. A test against a real dependency finds real bugs; a mock only ever
confirms your assumptions. Mock at the network boundary when the dependency is a third party,
costs money, or cannot produce the state you need.

```python
# Prefer monkeypatch over unittest.mock.patch for module attributes: it undoes
# itself at teardown, so there is no decorator stack and no leaked patch.
def test_retry_gives_up_after_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def fake_send(*_args, **_kwargs) -> None:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(mailer, "_send", fake_send)

    with pytest.raises(DeliveryFailed):
        mailer.deliver(message)
    assert attempts == MAX_RETRY_ATTEMPTS
```

For HTTP specifically, mock the transport (`respx`) rather than your own client wrapper — see
`api-httpx.md`. Mocking your wrapper tests the mock; mocking the transport tests your wrapper.

---

## Assertions

pytest rewrites plain `assert`, so you get the full comparison on failure. Use it.

```python
assert response.status_code == HTTP_CREATED          # shows both values on failure
assert user.roles == ["admin"]                       # shows the diff
```

For exceptions, assert on the type **and** something about the message — a bare `pytest.raises`
passes when the right exception is raised for the wrong reason:

```python
with pytest.raises(ValidationError, match="email"):
    UserCreate(email="not-an-email")
```

For floats, `pytest.approx`. For unordered collections, compare sets or sort — never rely on
incidental ordering:

```python
assert total == pytest.approx(19.99, abs=0.01)
assert set(returned_ids) == {user_a.id, user_b.id}
```

---

## Logging and Output

```python
def test_warns_on_deprecated_field(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        parse_payload({"legacy_id": 1})
    assert "legacy_id is deprecated" in caplog.text
```

`caplog`, `capsys`, `tmp_path`, `monkeypatch` are built in. Reach for them before writing a
fixture that does the same thing worse.
