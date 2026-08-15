from pathlib import Path

from fastapi.testclient import TestClient

from jolt.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"))


def _count(items: list[dict[str, object]], label: str) -> int:
    for item in items:
        if item["label"] == label:
            return int(item["count"])
    return 0


def test_market_separates_required_preferred_and_plain_skill_mentions(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)

    postings = [
        (
            "https://example.test/required",
            "Technical Support Engineer",
            "Requirements: SQL and PowerShell. Support Windows incidents.",
        ),
        (
            "https://example.test/preferred",
            "Application Support Engineer",
            "Azure preferred. Nice to have ServiceNow. Support API incidents.",
        ),
        (
            "https://example.test/mandatory",
            "Production Support Engineer",
            "Linux is mandatory. SQL is desirable. Troubleshoot DNS incidents.",
        ),
    ]

    for source_url, title, description in postings:
        response = client.post(
            "/api/intake/manual",
            json={
                "source_type": "manual",
                "source_url": source_url,
                "raw_text": (f"{title}\nExample Company\nLocation: Remote Spain\n{description}"),
            },
        )
        assert response.status_code == 200

    payload = client.get("/api/market-intelligence?timeframe=all&source_scope=manual_intake").json()
    scope = payload["all"]

    assert _count(scope["required_skills"], "SQL") == 1
    assert _count(scope["required_skills"], "Powershell") == 1
    assert _count(scope["required_skills"], "Linux") == 1

    assert _count(scope["preferred_skills"], "Azure") == 1
    assert _count(scope["preferred_skills"], "Servicenow") == 1
    assert _count(scope["preferred_skills"], "SQL") == 1

    assert _count(scope["mentioned_skills"], "Windows") == 1
    assert _count(scope["mentioned_skills"], "API") == 1
    assert _count(scope["mentioned_skills"], "DNS") == 1

    assert _count(scope["top_skills"], "SQL") == 2
    assert _count(scope["top_skills"], "Windows") == 1
