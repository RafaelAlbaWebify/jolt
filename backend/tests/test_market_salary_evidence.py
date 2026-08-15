from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def test_market_salary_coverage_is_a_real_ratio_and_one_card_per_role(
    tmp_path: Path,
) -> None:
    client = TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))

    first = client.post(
        "/api/intake/manual",
        json={
            "source_type": "manual",
            "source_url": "https://example.test/salary-role",
            "raw_text": (
                "Technical Support Engineer\n"
                "Salary Company\n"
                "Location: Remote Spain\n"
                "Support Windows and API incidents. "
                "Salary €45,000 - €50,000 per year."
            ),
        },
    )
    second = client.post(
        "/api/intake/manual",
        json={
            "source_type": "manual",
            "source_url": "https://example.test/no-salary-role",
            "raw_text": (
                "Application Support Engineer\n"
                "No Salary Company\n"
                "Location: Remote Spain\n"
                "Support SQL applications and incidents."
            ),
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    payload = client.get("/api/market-intelligence?timeframe=all&source_scope=manual_intake").json()

    scope = payload["target"]

    assert scope["total_roles"] == 2
    assert scope["salary_role_count"] == 1
    assert scope["salary_coverage"] == 0.5
    assert scope["salary_coverage_percent"] == 50.0

    assert len(scope["salary_mentions"]) == 1
    assert scope["salary_mentions"][0]["title"] == ("Technical Support Engineer")
    assert scope["salary_mentions"][0]["company"] == ("Salary Company")
    assert "€45,000" in scope["salary_mentions"][0]["mention"]
    assert "€50,000" in scope["salary_mentions"][0]["mention"]
