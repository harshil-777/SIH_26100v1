"""Request validation and error shaping that happen before any database access."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture(scope="module")
def client():
    @app.get("/__test_unhandled_error")
    async def _boom():
        raise RuntimeError("boom")

    yield TestClient(app, raise_server_exceptions=False)
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/__test_unhandled_error"]


def test_unhandled_error_is_a_json_500_that_keeps_cors_headers(client):
    response = client.get("/__test_unhandled_error", headers=ORIGIN)
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error. Please try again."}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


@pytest.mark.parametrize("decision", ["disqualify", "request_clarification"])
def test_adverse_decision_without_a_reason_is_rejected(client, decision):
    response = client.post("/bids/ANY/decision", json={"decision": decision, "actor": "officer"}, headers=ORIGIN)
    assert response.status_code == 422
    assert "A reason is required" in response.text


def test_decision_needs_a_named_actor(client):
    response = client.post("/bids/ANY/decision", json={"decision": "qualify", "actor": ""})
    assert response.status_code == 422


def test_unknown_decision_value_is_rejected(client):
    response = client.post("/bids/ANY/decision", json={"decision": "approve", "actor": "o", "reason": "x"})
    assert response.status_code == 422
