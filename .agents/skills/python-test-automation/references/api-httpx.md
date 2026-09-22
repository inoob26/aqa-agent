# API Testing with httpx

The Python counterpart to `api-testing`. That skill defines *what* to assert — response shape,
status codes, headers, auth boundaries, timing. This file is the Python implementation.

## Client Fixtures

```python
# tests/api/conftest.py
from collections.abc import Iterator

import httpx
import pytest

CONNECT_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 10.0


@pytest.fixture(scope="session")
def api_client(base_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(
        base_url=base_url,
        timeout=httpx.Timeout(READ_TIMEOUT_S, connect=CONNECT_TIMEOUT_S),
        # Redirects are behavior. Following them silently hides a 301 that should
        # have been a 200, and turns an auth redirect into a confusing 200 on /login.
        follow_redirects=False,
        headers={"User-Agent": "qa-suite/1.0"},
    ) as client:
        yield client
```

Session scope is correct here and only here: the client is a connection pool with no per-test
state. Anything that carries a token, a cookie, or a created entity is function-scoped.

### Never build a client at module level

```python
# Wrong: never closed, leaks sockets, multiplied by every xdist worker.
client = httpx.Client(base_url="https://api.example.com")

# Right: a fixture with the context manager.
@pytest.fixture(scope="session")
def api_client() -> Iterator[httpx.Client]: ...
```

---

## Authentication

Each mechanism needs a different fixture shape. All of them keep the token out of the shared
client's permanent state.

### Bearer token

```python
@pytest.fixture
def authed_client(api_client: httpx.Client) -> Iterator[httpx.Client]:
    token = api_client.post(
        "/auth/login",
        json={"email": os.environ["QA_USER"], "password": os.environ["QA_PASSWORD"]},
    ).raise_for_status().json()["access_token"]

    api_client.headers["Authorization"] = f"Bearer {token}"
    yield api_client
    del api_client.headers["Authorization"]
```

### Custom auth flow as an httpx.Auth

Cleaner than header juggling when the token must refresh mid-suite:

```python
class BearerAuth(httpx.Auth):
    def __init__(self, token_provider: Callable[[], str]) -> None:
        self._token_provider = token_provider

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._token_provider()}"
        response = yield request
        if response.status_code == HTTP_UNAUTHORIZED:
            # Refresh once and retry — mirrors what the real client does.
            self._token_provider.cache_clear()
            request.headers["Authorization"] = f"Bearer {self._token_provider()}"
            yield request
```

### The auth boundary is itself a test suite

Hardcoding a valid token and never testing the negative cases is the most common gap in an API
suite:

```python
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403


def test_missing_token_is_rejected(api_client: httpx.Client) -> None:
    assert api_client.get("/users/me").status_code == HTTP_UNAUTHORIZED


def test_expired_token_is_rejected(api_client: httpx.Client, expired_token: str) -> None:
    response = api_client.get("/users/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == HTTP_UNAUTHORIZED
    assert "expired" in response.json()["detail"].lower()


def test_viewer_cannot_delete_another_users_order(viewer_client: httpx.Client,
                                                  other_users_order: Order) -> None:
    # Authorization, not authentication: a valid token for the wrong user.
    assert viewer_client.delete(f"/orders/{other_users_order.id}").status_code == HTTP_FORBIDDEN


def test_malformed_token_does_not_500(api_client: httpx.Client) -> None:
    response = api_client.get("/users/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == HTTP_UNAUTHORIZED
```

---

## Schema as Contract

A Pydantic model is the assertion. It checks presence, type, format and — with
`extra="forbid"` — absence of anything unexpected.

```python
# tests/api/schemas.py
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class OrderStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    CANCELLED = "cancelled"


class StrictModel(BaseModel):
    # Shared base: an added field fails the test, which is how you find out the API
    # changed before your consumers do.
    model_config = ConfigDict(extra="forbid")


class OrderItem(StrictModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0)


class OrderResponse(StrictModel):
    id: int
    status: OrderStatus              # an unknown status value fails here
    customer_email: EmailStr
    items: list[OrderItem] = Field(min_length=1)
    total: Decimal
    invoice_url: HttpUrl | None = None
    created_at: datetime


class Page(StrictModel):
    items: list[OrderResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(gt=0)
```

Generate the models from the spec when one exists — hand-written schemas drift:

```bash
datamodel-codegen --input openapi.json --output tests/api/schemas.py \
                  --target-python-version 3.12 --use-standard-collections
```

A helper that makes the failure readable:

```python
def validate(model: type[T], response: httpx.Response) -> T:
    try:
        return model.model_validate(response.json())
    except ValidationError as exc:
        pytest.fail(
            f"{response.request.method} {response.request.url} "
            f"returned {response.status_code} that violates {model.__name__}:\n"
            f"{exc}\n\nBody: {response.text[:2000]}"
        )
```

---

## CRUD Lifecycle

One test per operation, sharing a fixture — not one test that does all four. A single lifecycle
test tells you "something in CRUD broke" and nothing more.

```python
HTTP_OK, HTTP_CREATED, HTTP_NO_CONTENT, HTTP_NOT_FOUND = 200, 201, 204, 404


@pytest.fixture
def created_order(authed_client: httpx.Client) -> Iterator[OrderResponse]:
    response = authed_client.post("/orders", json={"items": [{"sku": "ABC-1", "quantity": 2}]})
    assert response.status_code == HTTP_CREATED
    order = validate(OrderResponse, response)
    yield order
    # Cleanup tolerates an already-deleted order: the delete test removes it itself.
    authed_client.delete(f"/orders/{order.id}")


def test_create_returns_location_header(authed_client: httpx.Client) -> None:
    response = authed_client.post("/orders", json={"items": [{"sku": "ABC-1", "quantity": 1}]})
    assert response.status_code == HTTP_CREATED
    order = validate(OrderResponse, response)
    assert response.headers["location"].endswith(f"/orders/{order.id}")
    assert order.status is OrderStatus.PENDING


def test_read_returns_the_created_order(authed_client: httpx.Client,
                                        created_order: OrderResponse) -> None:
    fetched = validate(OrderResponse, authed_client.get(f"/orders/{created_order.id}"))
    assert fetched == created_order


def test_patch_updates_only_the_given_field(authed_client: httpx.Client,
                                            created_order: OrderResponse) -> None:
    updated = validate(
        OrderResponse,
        authed_client.patch(f"/orders/{created_order.id}", json={"status": "paid"}),
    )
    assert updated.status is OrderStatus.PAID
    assert updated.items == created_order.items      # PATCH must not clobber siblings
    assert updated.id == created_order.id


def test_delete_then_read_returns_404(authed_client: httpx.Client,
                                      created_order: OrderResponse) -> None:
    assert authed_client.delete(f"/orders/{created_order.id}").status_code == HTTP_NO_CONTENT
    assert authed_client.get(f"/orders/{created_order.id}").status_code == HTTP_NOT_FOUND
```

---

## Pagination, Filtering, Errors

```python
@pytest.mark.parametrize("per_page", [1, 10, 100])
def test_page_size_is_respected(authed_client: httpx.Client, per_page: int) -> None:
    page = validate(Page, authed_client.get("/orders", params={"per_page": per_page}))
    assert len(page.items) <= per_page
    assert page.per_page == per_page


def test_pages_do_not_overlap(authed_client: httpx.Client) -> None:
    first = validate(Page, authed_client.get("/orders", params={"page": 1, "per_page": 5}))
    second = validate(Page, authed_client.get("/orders", params={"page": 2, "per_page": 5}))
    assert not ({o.id for o in first.items} & {o.id for o in second.items})


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"page": 0}, 422),
        ({"page": -1}, 422),
        ({"per_page": 100_000}, 422),
        ({"page": "abc"}, 422),
        ({"page": 999_999}, 200),      # beyond the end is empty, not an error
    ],
    ids=["page-zero", "page-negative", "per-page-too-large", "page-not-a-number", "past-the-end"],
)
def test_pagination_boundaries(authed_client: httpx.Client, params: dict,
                               expected_status: int) -> None:
    assert authed_client.get("/orders", params=params).status_code == expected_status
```

Error bodies are part of the contract too:

```python
class ErrorResponse(StrictModel):
    detail: str
    code: str


def test_not_found_returns_structured_error(authed_client: httpx.Client) -> None:
    response = authed_client.get("/orders/99999999")
    assert response.status_code == HTTP_NOT_FOUND
    error = validate(ErrorResponse, response)
    assert error.code == "order_not_found"
    # Error bodies must not leak internals.
    assert "Traceback" not in response.text
    assert "sqlalchemy" not in response.text.lower()
```

---

## Headers and Timing

```python
MAX_P95_MS = 500


def test_security_headers_present(api_client: httpx.Client) -> None:
    headers = api_client.get("/health").headers
    assert headers["content-type"].startswith("application/json")
    assert headers.get("x-content-type-options") == "nosniff"
    assert "strict-transport-security" in headers


def test_list_endpoint_responds_within_budget(authed_client: httpx.Client) -> None:
    response = authed_client.get("/orders")
    # response.elapsed covers the request only — good enough for a regression guard,
    # not a substitute for load testing.
    assert response.elapsed.total_seconds() * 1000 < MAX_P95_MS


def test_cors_allows_the_frontend_origin(api_client: httpx.Client) -> None:
    response = api_client.options(
        "/orders",
        headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
```

---

## GraphQL

One POST endpoint, so the assertions move into the body. The trap: GraphQL returns **200 with an
`errors` array** for a failed query, so a status-code-only test passes on every failure.

```python
GRAPHQL_URL = "/graphql"


def gql(client: httpx.Client, query: str, variables: dict | None = None) -> dict:
    response = client.post(GRAPHQL_URL, json={"query": query, "variables": variables or {}})
    assert response.status_code == HTTP_OK
    body = response.json()
    assert "errors" not in body, body["errors"]
    return body["data"]


def test_order_query_returns_requested_fields(authed_client: httpx.Client,
                                              created_order: OrderResponse) -> None:
    data = gql(
        authed_client,
        """
        query Order($id: ID!) {
          order(id: $id) { id status total items { sku quantity } }
        }
        """,
        {"id": str(created_order.id)},
    )
    order = validate_dict(OrderQueryResult, data["order"])
    assert order.status is OrderStatus.PENDING


def test_unauthorized_field_returns_graphql_error(viewer_client: httpx.Client) -> None:
    response = viewer_client.post(
        GRAPHQL_URL, json={"query": "{ adminStats { revenue } }"}
    )
    assert response.status_code == HTTP_OK          # GraphQL says 200
    body = response.json()
    assert body["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    assert body["data"]["adminStats"] is None
```

Guard against schema drift with an introspection snapshot compared in CI — a removed field is a
breaking change even when every existing query still passes.

---

## Mocking with respx

Mock the **transport**, not your own wrapper. Mocking the wrapper tests the mock.

```python
import httpx
import respx


@respx.mock
def test_payment_timeout_is_retried_then_surfaced() -> None:
    route = respx.post("https://psp.example.com/charge").mock(
        side_effect=[httpx.TimeoutException("timeout"), httpx.Response(200, json={"ok": True})]
    )
    result = charge_card(amount=1000)

    assert result.ok
    assert route.call_count == 2


@respx.mock
def test_psp_500_maps_to_domain_error() -> None:
    respx.post("https://psp.example.com/charge").mock(return_value=httpx.Response(500))

    with pytest.raises(PaymentProviderUnavailable):
        charge_card(amount=1000)


@respx.mock
def test_request_body_matches_psp_contract() -> None:
    route = respx.post("https://psp.example.com/charge").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    charge_card(amount=1000, currency="CZK")

    request = route.calls.last.request
    assert json.loads(request.content) == {"amount": 1000, "currency": "CZK"}
    assert request.headers["idempotency-key"]
```

Use `assert_all_called` (respx's default) so a mock that was never hit fails the test — an unused
mock usually means the code took a path you didn't expect.

---

## In-Process Testing (ASGI)

Fastest feedback for FastAPI/Starlette/Django-ASGI apps: no server, no port, no network.

```python
import httpx
import pytest
from app.main import app


@pytest.fixture
async def asgi_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_health(asgi_client: httpx.AsyncClient) -> None:
    response = await asgi_client.get("/health")
    assert response.status_code == HTTP_OK
```

What this does **not** cover: TLS, the reverse proxy, real middleware ordering under a server,
connection limits, and anything the deployment adds. Keep a small over-the-wire smoke suite
against a deployed environment for those.

---

## Async Polling

The correct replacement for `time.sleep()` when waiting on a background job:

```python
POLL_INTERVAL_S = 0.5
POLL_DEADLINE_S = 30.0


def wait_for_status(client: httpx.Client, order_id: int, expected: OrderStatus) -> OrderResponse:
    deadline = time.monotonic() + POLL_DEADLINE_S
    last: OrderResponse | None = None
    while time.monotonic() < deadline:
        last = validate(OrderResponse, client.get(f"/orders/{order_id}"))
        if last.status is expected:
            return last
        time.sleep(POLL_INTERVAL_S)
    pytest.fail(
        f"Order {order_id} never reached {expected} within {POLL_DEADLINE_S}s; "
        f"last status was {last.status if last else 'unknown'}"
    )
```

The difference from a bare sleep: it returns as soon as the condition holds, it has an explicit
deadline, and the failure message says what the state actually was.
