from fastapi.testclient import TestClient

from app.main import app


def test_health_exposes_security_and_trace_headers():
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "test-request-42"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "test-request-42"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "geolocation=(), microphone=(), camera=()"


def test_api_responses_are_not_cacheable():
    client = TestClient(app)
    response = client.get("/api/dashboard-summary")

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
