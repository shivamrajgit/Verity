from fastapi.testclient import TestClient

import server
from server import app


def test_health_and_frontend_routes() -> None:
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200
    assert client.get("/").status_code == 200


def test_server_rejects_config_traversal() -> None:
    client = TestClient(app)

    response = client.get(
        "/api/run",
        params={"url": "https://example.com", "config": "../.env"},
    )

    assert response.status_code == 400


def test_protected_endpoints_require_configured_token(monkeypatch) -> None:
    monkeypatch.setenv("VERITY_API_TOKEN", "test-token")
    client = TestClient(app)

    assert client.get("/api/health").status_code == 200
    assert client.get("/api/run", params={"url": "https://example.com"}).status_code == 401
    assert (
        client.get(
            "/api/run",
            params={"url": "https://example.com", "config": "../.env"},
            headers={"X-API-Key": "test-token"},
        ).status_code
        == 400
    )


def test_protected_sse_accepts_authenticated_session_cookie(monkeypatch) -> None:
    monkeypatch.setenv("VERITY_API_TOKEN", "test-token")
    client = TestClient(app)

    auth = client.post("/api/auth", headers={"X-API-Key": "test-token"})

    assert auth.status_code == 200
    assert (
        client.get(
            "/api/run",
            params={"url": "https://example.com", "config": "../.env"},
        ).status_code
        == 400
    )


def test_run_endpoint_rate_limits_by_ip(monkeypatch) -> None:
    monkeypatch.delenv("VERITY_API_TOKEN", raising=False)
    monkeypatch.setenv("VERITY_RATE_LIMIT_RUNS", "3")
    monkeypatch.setenv("VERITY_RATE_LIMIT_WINDOW_SECONDS", "3600")
    server._RATE_LIMIT_HITS.clear()

    client = TestClient(app)
    # A traversal config makes each allowed request 400 out *before* a real run
    # starts, so we exercise the limiter without invoking the agent pipeline.
    params = {"url": "https://example.com", "config": "../.env"}

    for _ in range(3):
        assert client.get("/api/run", params=params).status_code == 400

    blocked = client.get("/api/run", params=params)
    assert blocked.status_code == 429
    assert "retry-after" in {key.lower() for key in blocked.headers}

    server._RATE_LIMIT_HITS.clear()
