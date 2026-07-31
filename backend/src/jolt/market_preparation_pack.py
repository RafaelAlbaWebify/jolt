from __future__ import annotations

import csv
import hashlib
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Evaluation, Posting
from jolt.job_search_preferences import load_job_search_preferences
from jolt.linkedin_command_center import list_linkedin_command_center
from jolt.market_intelligence import build_market_intelligence
from jolt.strategy_runtime import ENGINE_VERSION


def _csv_bytes(rows: list[dict[str, object]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _latest_evaluations(session: Session) -> dict[str, Evaluation]:
    evaluations = session.scalars(
        select(Evaluation)
        .where(Evaluation.engine_version == ENGINE_VERSION)
        .order_by(Evaluation.created_at.desc())
    ).all()
    latest: dict[str, Evaluation] = {}
    for evaluation in evaluations:
        latest.setdefault(evaluation.posting_id, evaluation)
    return latest


def _job_rows(session: Session) -> list[dict[str, object]]:
    evaluations = _latest_evaluations(session)
    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()
    rows: list[dict[str, object]] = []
    for posting in postings:
        evaluation = evaluations.get(posting.id)
        rows.append(
            {
                "id": posting.id,
                "title": posting.title,
                "company": posting.company,
                "location": posting.location,
                "canonical_url": posting.canonical_url,
                "identity_status": posting.identity_status,
                "created_at": posting.created_at.isoformat(),
                "description_excerpt": posting.description[:2500],
                "recommendation": evaluation.recommendation if evaluation else "",
                "confidence": evaluation.confidence if evaluation else "",
                "ranking_score": evaluation.ranking_score if evaluation else None,
                "evaluation_reasons": json.loads(evaluation.reasons_json) if evaluation else [],
                "evaluated_at": evaluation.created_at.isoformat() if evaluation else "",
            }
        )
    return rows


def build_market_preparation_pack(session: Session) -> bytes:
    preferences = load_job_search_preferences()
    market = build_market_intelligence(session, timeframe="all", source_scope="all")
    linkedin = list_linkedin_command_center(session).model_dump()
    jobs = _job_rows(session)
    dataset = {
        "pack_type": "jolt_market_linkedin_preparation",
        "pack_version": 1,
        "purpose": "Analyze Rafael's target job market, LinkedIn positioning, and preparation priorities.",
        "job_search_preferences": preferences.model_dump(),
        "market_intelligence": market,
        "linkedin_command_center": linkedin,
        "jobs": jobs,
        "import_contract": {
            "expected_return_zip": "JOLT_MARKET_PREPARATION_RETURN.zip",
            "expected_files": [
                "market_preparation_recommendations.json",
                "study_plan.md",
                "search_filter_improvements.md",
                "linkedin_alignment_actions.md",
                "application_strategy.md",
            ],
            "future_jolt_import_target": "reviewable market/preparation actions",
        },
    }
    prompt = """# JOLT Market + LinkedIn Preparation Analysis Prompt

You are analyzing Rafael Alba's JOLT export. Act as a disciplined career-market analyst, application-support hiring analyst, LinkedIn positioning reviewer, and practical study-plan designer.

Use the files in this package, especially:

- `data/market_linkedin_preparation.json`
- `data/jobs.csv`
- `data/linkedin_recommendations.csv`
- `data/job_search_preferences.json`

## Objectives

1. Identify which captured job offers are truly aligned with Rafael's target path.
2. Identify noisy/outside-target job types that should be filtered out.
3. Compare target-market requirements against Rafael's LinkedIn positioning and imported LinkedIn recommendations.
4. Produce a practical preparation plan: what to study, what to practice, what proof-of-work to create, what to update on LinkedIn, and what to say in interviews.
5. Respect the job search preferences, including remote/hybrid preferences, max distance, shifts, workload, salary expectations, excluded keywords, and target roles.

## Hard rules

- Do not invent private facts beyond the exported evidence.
- Do not suggest automating LinkedIn actions, mass messaging, scraping, or deceptive activity.
- Prefer evidence-backed recommendations over generic career advice.
- Keep recommendations practical for Rafael's profile: IT Ops / Application Support / Technical Support / Production Support / SaaS Support.
- Separate high-confidence conclusions from uncertain hypotheses.

## Return package

Return a ZIP named `JOLT_MARKET_PREPARATION_RETURN.zip` containing:

1. `market_preparation_recommendations.json` with this shape:

```json
{
  "source": "chatgpt_market_preparation_package",
  "recommendations": [
    {
      "recommendation_type": "study | practice | linkedin_update | search_filter | application_strategy | proof_of_work | interview_prep",
      "target_area": "SQL troubleshooting, LinkedIn headline, search filters, etc.",
      "title": "Short action title",
      "rationale": "Evidence-based reason",
      "proposed_action": "Manual action Rafael should take",
      "proposed_text": "Optional exact text, query, bullet, or study exercise",
      "priority": "high | medium | low",
      "evidence_refs": ["job title/company, market skill, LinkedIn recommendation, preference rule"]
    }
  ]
}
```

2. `study_plan.md` — 2 to 4 week study/practice plan.
3. `search_filter_improvements.md` — concrete changes to job searches and exclusions.
4. `linkedin_alignment_actions.md` — profile/content/proof-of-work actions aligned with market demand.
5. `application_strategy.md` — what to apply to, what to avoid, and interview positioning.
6. `analysis_summary.md` — concise executive summary.
"""
    readme = f"""# JOLT Market + LinkedIn Preparation Pack

This package is for a ChatGPT analysis round that combines:

- active job-offer market evidence;
- JOLT Market Insights;
- LinkedIn Command Center captures/recommendations;
- editable job search preferences.

Dataset size:

- Jobs: {len(jobs)}
- LinkedIn captures: {linkedin.get('capture_count', 0)}
- LinkedIn recommendations: {linkedin.get('recommendation_count', 0)}
- Target roles in market view: {market.get('target_role_count', 0)}

Upload this ZIP to ChatGPT and use `prompt.md` as the operating instruction.
"""
    linkedin_recommendations = linkedin.get("recommendations", [])
    files = {
        "README.md": readme.encode("utf-8"),
        "prompt.md": prompt.encode("utf-8"),
        "data/market_linkedin_preparation.json": json.dumps(dataset, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        "data/job_search_preferences.json": json.dumps(preferences.model_dump(), indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8"),
        "data/jobs.csv": _csv_bytes(
            jobs,
            [
                "id",
                "title",
                "company",
                "location",
                "canonical_url",
                "identity_status",
                "created_at",
                "recommendation",
                "confidence",
                "ranking_score",
                "evaluated_at",
            ],
        ),
        "data/linkedin_recommendations.csv": _csv_bytes(
            linkedin_recommendations,
            [
                "id",
                "recommendation_type",
                "target_area",
                "title",
                "rationale",
                "proposed_action",
                "priority",
                "status",
                "created_at",
                "updated_at",
            ],
        ),
    }
    manifest = {
        "pack_type": dataset["pack_type"],
        "pack_version": dataset["pack_version"],
        "files": {
            name: {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in sorted(files.items())
        },
    }
    files["manifest.json"] = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()
