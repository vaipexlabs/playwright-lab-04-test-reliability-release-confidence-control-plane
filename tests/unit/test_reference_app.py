from fastapi.testclient import TestClient

from vaipex_test_reliability.app import app, scenario_state

client = TestClient(app)


def setup_function() -> None:
    scenario_state.reset()


def test_readiness_contract() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_stable_checkout_succeeds_immediately() -> None:
    response = client.post("/api/checkout?scenario=stable")

    assert response.status_code == 200
    assert response.json()["outcome"] == "confirmed"
    assert response.json()["attempt"] == 1


def test_transient_checkout_recovers_deterministically() -> None:
    first = client.post("/api/checkout?scenario=transient")
    second = client.post("/api/checkout?scenario=transient")

    assert first.status_code == 503
    assert first.json()["outcome"] == "transient-failure"
    assert second.status_code == 200
    assert second.json()["outcome"] == "confirmed"


def test_critical_checkout_remains_failed() -> None:
    first = client.post("/api/checkout?scenario=critical-failure")
    second = client.post("/api/checkout?scenario=critical-failure")

    assert first.status_code == 503
    assert second.status_code == 503
    assert second.json()["attempt"] == 2
