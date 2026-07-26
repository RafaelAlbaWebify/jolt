from __future__ import annotations

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Expected marker not found: {label}")
    return text.replace(old, new, 1)


def add_authority_module(root: Path) -> None:
    path = root / "backend/src/jolt/evaluation_authority.py"
    path.write_text(
        '''from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_readiness import ApplicationReadiness
from jolt.database import Evaluation
from jolt.strategy_runtime import ENGINE_VERSION as STRATEGY_ENGINE_VERSION


def authoritative_evaluations(session: Session) -> dict[str, Evaluation]:
    """Select one stable evaluation per posting without creating derived records."""
    evaluations = session.scalars(select(Evaluation).order_by(Evaluation.created_at.desc())).all()
    strategy: dict[str, Evaluation] = {}
    fallback: dict[str, Evaluation] = {}
    for evaluation in evaluations:
        fallback.setdefault(evaluation.posting_id, evaluation)
        if evaluation.engine_version == STRATEGY_ENGINE_VERSION:
            strategy.setdefault(evaluation.posting_id, evaluation)
    return {posting_id: strategy.get(posting_id, evaluation) for posting_id, evaluation in fallback.items()}


def authoritative_evaluation(session: Session, posting_id: str) -> Evaluation | None:
    return authoritative_evaluations(session).get(posting_id)


def latest_readiness_report(session: Session, posting_id: str) -> ApplicationReadiness | None:
    return session.scalar(
        select(ApplicationReadiness)
        .where(ApplicationReadiness.posting_id == posting_id)
        .order_by(ApplicationReadiness.created_at.desc())
    )
''',
        encoding="utf-8",
    )


def patch_opportunity_index(root: Path) -> None:
    path = root / "backend/src/jolt/opportunity_index.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(text, "from jolt.automated_review import ensure_automated_reviews\n", "", "remove lazy review import")
    text = replace_once(
        text,
        "from jolt.database import (\n",
        "from jolt.database import (\n",
        "database import anchor",
    )
    text = replace_once(
        text,
        ")\n\n\nclass OpportunityIndexItem",
        ")\nfrom jolt.evaluation_authority import authoritative_evaluations\n\n\nclass OpportunityIndexItem",
        "authority import",
    )
    text = replace_once(
        text,
        '''    """Return compact queue metadata without constructing full review detail."""\n    ensure_automated_reviews(session)\n\n    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()\n''',
        '''    """Return compact queue metadata without constructing full review detail."""\n    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()\n''',
        "remove GET write",
    )
    old = '''    latest_evaluations: dict[str, Evaluation] = {}\n    for evaluation in session.scalars(\n        select(Evaluation).order_by(Evaluation.created_at.desc())\n    ).all():\n        latest_evaluations.setdefault(evaluation.posting_id, evaluation)\n'''
    text = replace_once(text, old, "    latest_evaluations = authoritative_evaluations(session)\n", "authoritative queue evaluations")
    text = text.replace("    Evaluation,\n", "", 1)
    path.write_text(text, encoding="utf-8")


def patch_workbench(root: Path) -> None:
    path = root / "backend/src/jolt/opportunity_workbench.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from jolt.application_readiness import ensure_readiness_report, readiness_payload\n",
        "from jolt.application_readiness import readiness_payload\n",
        "read-only readiness import",
    )
    text = replace_once(
        text,
        "from jolt.automated_review import analyze_posting, ensure_automated_reviews\n",
        "from jolt.automated_review import analyze_posting\n",
        "remove automated ensure import",
    )
    text = replace_once(
        text,
        "from jolt.database import Application, Evaluation, Outcome, Posting, ReviewDecision\n",
        "from jolt.database import Application, Outcome, Posting, ReviewDecision\n",
        "remove direct evaluation import",
    )
    text = replace_once(
        text,
        "from jolt.evaluation_strategy import StrategyAssessment\n",
        "from jolt.evaluation_authority import authoritative_evaluation, latest_readiness_report\nfrom jolt.evaluation_strategy import StrategyAssessment, assess_posting\n",
        "authority and pure assessment imports",
    )
    text = replace_once(
        text,
        '''from jolt.strategy_runtime import (\n    ensure_strategy_review,\n    ensure_strategy_reviews,\n    latest_strategy_evaluation,\n    load_active_strategy_profile,\n    proposed_decision,\n)\n''',
        '''from jolt.strategy_runtime import (\n    ENGINE_VERSION as STRATEGY_ENGINE_VERSION,\n    load_active_strategy_profile,\n    proposed_decision,\n)\n''',
        "remove strategy writes",
    )
    text = replace_once(
        text,
        '''def _build_summary(\n    session: Session,\n    posting: Posting,\n    assessment: StrategyAssessment | None,\n) -> OpportunitySummary | None:\n    legacy_evaluation = session.scalar(\n        select(Evaluation)\n        .where(Evaluation.posting_id == posting.id)\n        .order_by(Evaluation.created_at.desc())\n    )\n    if legacy_evaluation is None:\n        return None\n\n    strategy_evaluation = latest_strategy_evaluation(session, posting.id) if assessment else None\n    evaluation = strategy_evaluation or legacy_evaluation\n    legacy_analysis = analyze_posting(posting.title, posting.location, posting.description)\n\n    readiness_report = ensure_readiness_report(session, posting)\n    readiness = ApplicationReadinessSummary.model_validate(readiness_payload(readiness_report))\n''',
        '''def _build_summary(session: Session, posting: Posting) -> OpportunitySummary | None:\n    evaluation = authoritative_evaluation(session, posting.id)\n    if evaluation is None:\n        return None\n\n    profile = load_active_strategy_profile()\n    assessment: StrategyAssessment | None = None\n    if profile is not None and evaluation.engine_version == STRATEGY_ENGINE_VERSION:\n        assessment = assess_posting(profile, posting.title, posting.location, posting.description)\n    legacy_analysis = analyze_posting(posting.title, posting.location, posting.description)\n\n    readiness_report = latest_readiness_report(session, posting.id)\n    readiness = (\n        ApplicationReadinessSummary.model_validate(readiness_payload(readiness_report))\n        if readiness_report is not None\n        else None\n    )\n''',
        "read-only summary boundary",
    )
    text = replace_once(
        text,
        '''def list_opportunity_workbench(session: Session) -> list[OpportunitySummary]:\n    ensure_automated_reviews(session)\n    profile = load_active_strategy_profile()\n    strategy_assessments = ensure_strategy_reviews(session, profile) if profile else {}\n    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()\n    return [\n        summary\n        for posting in postings\n        if (summary := _build_summary(session, posting, strategy_assessments.get(posting.id)))\n        is not None\n    ]\n''',
        '''def list_opportunity_workbench(session: Session) -> list[OpportunitySummary]:\n    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()\n    return [\n        summary\n        for posting in postings\n        if (summary := _build_summary(session, posting)) is not None\n    ]\n''',
        "read-only list",
    )
    text = replace_once(
        text,
        '''def get_opportunity_workbench(session: Session, posting_id: str) -> OpportunitySummary:\n    ensure_automated_reviews(session)\n    posting = session.get(Posting, posting_id)\n''',
        '''def get_opportunity_workbench(session: Session, posting_id: str) -> OpportunitySummary:\n    posting = session.get(Posting, posting_id)\n''',
        "read-only detail start",
    )
    text = replace_once(
        text,
        '''    profile = load_active_strategy_profile()\n    assessment = ensure_strategy_review(session, profile, posting) if profile else None\n    summary = _build_summary(session, posting, assessment)\n''',
        '''    summary = _build_summary(session, posting)\n''',
        "read-only detail assessment",
    )
    path.write_text(text, encoding="utf-8")


def patch_main(root: Path) -> None:
    path = root / "backend/src/jolt/main.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from jolt.application_preparation_pack import build_application_preparation_pack\n",
        "from jolt.application_preparation_pack import build_application_preparation_pack\nfrom jolt.automated_review import ensure_automated_reviews\n",
        "automated refresh import",
    )
    text = replace_once(
        text,
        "from jolt.schemas import (\n",
        "from jolt.schemas import (\n",
        "schemas anchor",
    )
    text = replace_once(
        text,
        ")\nfrom jolt.workflow import (\n",
        ")\nfrom jolt.strategy_runtime import ensure_strategy_reviews, load_active_strategy_profile\nfrom jolt.workflow import (\n",
        "strategy refresh imports",
    )
    anchor = '''    @app.get(\n        "/api/opportunity-index", response_model=list[OpportunityIndexItem], tags=["opportunities"]\n    )\n'''
    endpoint = '''    @app.post("/api/evaluations/refresh", tags=["opportunities"])\n    def refresh_evaluations(\n        session: Annotated[Session, Depends(get_session)],\n    ) -> dict[str, object]:\n        ensure_automated_reviews(session)\n        profile = load_active_strategy_profile()\n        assessments = ensure_strategy_reviews(session, profile) if profile is not None else {}\n        return {\n            "status": "refreshed",\n            "authoritative_engine": "profile-rules-v4" if profile is not None else "profile-rules-v2",\n            "strategy_evaluation_count": len(assessments),\n        }\n\n'''
    text = replace_once(text, anchor, endpoint + anchor, "explicit evaluation refresh endpoint")
    path.write_text(text, encoding="utf-8")


def patch_frontend(root: Path) -> None:
    path = root / "frontend/src/App.tsx"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''  const refreshOpportunities = useCallback(async () => {\n    setRefreshing(true);\n    try {\n      const response = await fetch(`${API_BASE}/api/opportunity-index`);\n''',
        '''  const refreshOpportunities = useCallback(async (recalculate = false) => {\n    setRefreshing(true);\n    setError("");\n    try {\n      if (recalculate) {\n        const refreshResponse = await fetch(`${API_BASE}/api/evaluations/refresh`, { method: "POST" });\n        if (!refreshResponse.ok) throw new Error("Unable to refresh opportunity evaluations.");\n      }\n      const response = await fetch(`${API_BASE}/api/opportunity-index`);\n''',
        "explicit frontend recalculation",
    )
    text = replace_once(
        text,
        '''    } finally {\n      setRefreshing(false);\n    }\n  }, []);\n''',
        '''    } catch (caught) {\n      const message = caught instanceof Error ? caught.message : "Unable to load opportunities.";\n      setError(message);\n      throw caught;\n    } finally {\n      setRefreshing(false);\n    }\n  }, []);\n''',
        "queue refresh error handling",
    )
    text = replace_once(
        text,
        "            onClick={() => void refreshOpportunities()}\n",
        "            onClick={() => void refreshOpportunities(true)}\n",
        "refresh button recalculation",
    )
    path.write_text(text, encoding="utf-8")


def patch_existing_tests(root: Path) -> None:
    path = root / "backend/tests/test_api.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    opportunities = restarted_client.get("/api/opportunities")\n    assert opportunities.status_code == 200\n''',
        '''    refresh = restarted_client.post("/api/evaluations/refresh")\n    assert refresh.status_code == 200\n    assert refresh.json()["authoritative_engine"] == "profile-rules-v4"\n\n    opportunities = restarted_client.get("/api/opportunities")\n    assert opportunities.status_code == 200\n''',
        "explicit refresh in API test",
    )
    text = replace_once(text, '    assert opportunity["profile_version_id"] == "rafael-job-search:v2"\n', '    assert opportunity["profile_version_id"].startswith("rafael-job-search:")\n', "profile expectation")
    text = replace_once(text, '    assert opportunity["engine_version"] == "profile-rules-v2"\n', '    assert opportunity["engine_version"] == "profile-rules-v4"\n', "engine expectation")
    text = replace_once(
        text,
        '''    opportunities = client.get("/api/opportunities")\n    assert opportunities.status_code == 200\n''',
        '''    refresh = client.post("/api/evaluations/refresh")\n    assert refresh.status_code == 200\n    opportunities = client.get("/api/opportunities")\n    assert opportunities.status_code == 200\n''',
        "explicit blocker refresh",
    )
    path.write_text(text, encoding="utf-8")


def add_tests(root: Path) -> None:
    path = root / "backend/tests/test_read_only_evaluation_authority.py"
    path.write_text(
        '''from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from jolt.application_readiness import ApplicationReadiness
from jolt.database import Evaluation, ProfileVersion, create_session_factory
from jolt.main import create_app


def _client(database_path: Path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{database_path.as_posix()}"))


def _derived_counts(database_path: Path) -> tuple[int, int, int]:
    factory = create_session_factory(f"sqlite:///{database_path.as_posix()}")
    with factory() as session:
        return (
            int(session.scalar(select(func.count(Evaluation.id))) or 0),
            int(session.scalar(select(func.count(ProfileVersion.id))) or 0),
            int(session.scalar(select(func.count(ApplicationReadiness.id))) or 0),
        )


def test_get_workspaces_do_not_create_derived_records(tmp_path: Path) -> None:
    database_path = tmp_path / "readonly.db"
    client = _client(database_path)
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/readonly",
            "raw_text": (
                "Application Support Engineer\\nExample Systems\\nLocation: Remote Spain\\n"
                "Application support, SQL troubleshooting, incident ownership, APIs, and monitoring."
            ),
        },
    )
    assert intake.status_code == 200
    posting_id = intake.json()["posting_id"]
    before = _derived_counts(database_path)

    for url in (
        "/api/opportunity-index",
        "/api/application-index",
        "/api/opportunities",
        f"/api/opportunity-detail/{posting_id}",
        "/api/market-intelligence",
    ):
        response = client.get(url)
        assert response.status_code == 200

    assert _derived_counts(database_path) == before


def test_explicit_refresh_creates_v4_and_all_reads_use_it(tmp_path: Path) -> None:
    database_path = tmp_path / "authority.db"
    client = _client(database_path)
    intake = client.post(
        "/api/intake/manual",
        json={
            "source_url": "https://example.com/jobs/authority",
            "raw_text": (
                "Production Support Engineer\\nExample Systems\\nLocation: Remote Spain\\n"
                "Production support, incident ownership, SQL, API integration, logs, and monitoring."
            ),
        },
    )
    assert intake.status_code == 200
    posting_id = intake.json()["posting_id"]

    refresh = client.post("/api/evaluations/refresh")
    assert refresh.status_code == 200
    assert refresh.json()["authoritative_engine"] == "profile-rules-v4"

    queue_item = client.get("/api/opportunity-index").json()[0]
    detail = client.get(f"/api/opportunity-detail/{posting_id}").json()
    list_item = client.get("/api/opportunities").json()[0]

    assert detail["engine_version"] == "profile-rules-v4"
    assert queue_item["evaluation_id"] == detail["evaluation_id"] == list_item["evaluation_id"]
    assert queue_item["ranking_score"] == detail["ranking_score"] == list_item["ranking_score"]

    before = _derived_counts(database_path)
    client.get("/api/opportunity-index")
    client.get(f"/api/opportunity-detail/{posting_id}")
    client.get("/api/opportunities")
    assert _derived_counts(database_path) == before
''',
        encoding="utf-8",
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    add_authority_module(root)
    patch_opportunity_index(root)
    patch_workbench(root)
    patch_main(root)
    patch_frontend(root)
    patch_existing_tests(root)
    add_tests(root)
    print("Evaluation authority and read-only GET patch applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
