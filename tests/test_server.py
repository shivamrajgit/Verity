from fastapi.testclient import TestClient

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
    monkeypatch.setenv("CRAGENT_API_TOKEN", "test-token")
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
