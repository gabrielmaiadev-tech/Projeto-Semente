from fastapi.testclient import TestClient

from vigia.main import create_app


def test_root_redirects_to_api_docs(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app, follow_redirects=False) as client:
        response = client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/docs"


def test_ingestion_groups_equivalent_events_and_reports_metrics(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app) as client:
        first = client.post(
            "/api/v1/events",
            json={"service": "checkout", "level": "error", "message": "Payment timeout"},
        )
        repeated = client.post(
            "/api/v1/events",
            json={
                "service": "checkout",
                "level": "error",
                "message": "  PAYMENT   TIMEOUT  ",
            },
        )
        metrics = client.get("/api/v1/metrics")

    assert first.status_code == 200
    assert repeated.status_code == 200
    assert first.json()["id"] == repeated.json()["id"]
    assert repeated.json()["occurrences"] == 2
    assert metrics.json() == {
        "total_incidents": 1,
        "total_occurrences": 2,
        "by_level": {"error": 1},
        "top_services": [{"service": "checkout", "incidents": 1, "occurrences": 2}],
    }


def test_incident_filters_and_pagination(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app) as client:
        client.post(
            "/api/v1/events",
            json={"service": "checkout", "level": "error", "message": "Payment timeout"},
        )
        client.post(
            "/api/v1/events",
            json={"service": "catalog", "level": "warning", "message": "Slow query"},
        )
        response = client.get("/api/v1/incidents?level=error&service=checkout&limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["service"] == "checkout"


def test_health_and_invalid_events(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app) as client:
        health = client.get("/health")
        invalid = client.post(
            "/api/v1/events",
            json={"service": "checkout", "level": "fatal", "message": "Oops"},
        )

    assert health.json() == {"status": "ok", "database": "connected"}
    assert invalid.status_code == 422