from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app

CONFIRMATION_PHRASE = "I UNDERSTAND THIS WILL OPEN LINKEDIN"


def test_preview_run_snapshots_plan_persists_and_can_be_cancelled(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))

    created = client.post("/api/professional-intelligence/capture-runs")

    assert created.status_code == 200
    run = created.json()
    assert run["mode"] == "preview_only"
    assert run["status"] == "planned"
    assert run["authorized_at"] is None
    assert run["authorization_expires_at"] is None
    assert run["user_present_confirmed"] is False
    assert run["started_at"] is None
    assert run["completed_at"] is None
    assert run["artifact_count"] == 0
    assert len(run["planned_sources"]) == 8
    assert "no_unattended_capture" in run["safety_constraints"]

    restarted = TestClient(create_app(database_url))
    history = restarted.get("/api/professional-intelligence/capture-runs")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [run["id"]]

    detail = restarted.get(f"/api/professional-intelligence/capture-runs/{run['id']}")
    assert detail.status_code == 200
    assert detail.json()["planned_sources"] == run["planned_sources"]

    cancelled = restarted.post(f"/api/professional-intelligence/capture-runs/{run['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["stop_reason"] == "cancelled_by_user"
    assert cancelled.json()["completed_at"] is not None

    repeated_cancel = restarted.post(
        f"/api/professional-intelligence/capture-runs/{run['id']}/cancel"
    )
    assert repeated_cancel.status_code == 409


def test_preview_run_requires_exact_user_present_authorization(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'authorization.db').as_posix()}"
    client = TestClient(create_app(database_url))
    run = client.post("/api/professional-intelligence/capture-runs").json()
    endpoint = f"/api/professional-intelligence/capture-runs/{run['id']}/authorize"

    wrong_phrase = client.post(
        endpoint,
        json={"confirmation_phrase": "OPEN LINKEDIN", "user_present": True},
    )
    assert wrong_phrase.status_code == 409

    absent_user = client.post(
        endpoint,
        json={"confirmation_phrase": CONFIRMATION_PHRASE, "user_present": False},
    )
    assert absent_user.status_code == 409

    authorized = client.post(
        endpoint,
        json={"confirmation_phrase": CONFIRMATION_PHRASE, "user_present": True},
    )
    assert authorized.status_code == 200
    payload = authorized.json()
    assert payload["status"] == "authorized"
    assert payload["authorized_at"] is not None
    assert payload["authorization_expires_at"] is not None
    assert payload["authorization_expires_at"] > payload["authorized_at"]
    assert payload["user_present_confirmed"] is True
    assert payload["started_at"] is None

    repeated = client.post(
        endpoint,
        json={"confirmation_phrase": CONFIRMATION_PHRASE, "user_present": True},
    )
    assert repeated.status_code == 409

    restarted = TestClient(create_app(database_url))
    persisted = restarted.get(f"/api/professional-intelligence/capture-runs/{run['id']}").json()
    assert persisted["status"] == "authorized"
    assert persisted["user_present_confirmed"] is True

    cancelled = restarted.post(f"/api/professional-intelligence/capture-runs/{run['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_preview_run_snapshot_is_immutable_after_registry_change(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    created = client.post("/api/professional-intelligence/capture-runs").json()
    client.post(
        "/api/professional-intelligence/sources/linkedin-profile/update",
        json={
            "label": "Changed after planning",
            "url": "https://www.linkedin.com/in/rafael-alba-tech/?changed=true",
            "initial_scope": False,
            "enabled": False,
        },
    )

    detail = client.get(f"/api/professional-intelligence/capture-runs/{created['id']}").json()
    profile = next(
        source for source in detail["planned_sources"] if source["source_id"] == "linkedin-profile"
    )
    assert profile["label"] == "Main profile"
    assert profile["initial_scope"] is True
    assert profile["enabled"] is True


def test_unknown_preview_run_returns_not_found(tmp_path: Path) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    response = client.get("/api/professional-intelligence/capture-runs/missing")

    assert response.status_code == 404
