from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.professional_intelligence_capture_runs import (
    ProfessionalCaptureRunResponse,
    effective_capture_run_status,
    get_professional_capture_run,
)
from jolt.professional_intelligence_evidence_contract import (
    DEFAULT_RETENTION_DAYS,
    ProfessionalArtifactManifestEntry,
    validate_professional_artifact_manifest_entry,
)
from jolt.professional_intelligence_evidence_root import (
    get_professional_evidence_root,
    resolve_professional_evidence_path,
)
from jolt.professional_intelligence_records import (
    ProfessionalCaptureArtifact,
    ProfessionalCaptureRun,
)
from jolt.professional_intelligence_sources import ProfessionalIntelligenceSource


@dataclass(frozen=True)
class CapturedProfessionalPage:
    screenshot_png: bytes
    visible_text: str
    title: str
    final_url: str
    http_status: int | None


CaptureSource = Callable[[str], CapturedProfessionalPage]


def capture_professional_source_visible(url: str) -> CapturedProfessionalPage:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        try:
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1_500)
            return CapturedProfessionalPage(
                screenshot_png=page.screenshot(full_page=True),
                visible_text=page.locator("body").inner_text(timeout=10_000),
                title=page.title(),
                final_url=page.url,
                http_status=response.status if response is not None else None,
            )
        finally:
            context.close()
            browser.close()


def _write_artifact(
    session: Session,
    *,
    root: Path,
    run_id: str,
    source_id: str,
    artifact_type: str,
    filename: str,
    content: bytes,
    completeness_status: str,
) -> None:
    relative_path = PurePosixPath("professional-intelligence", run_id, source_id, filename)
    absolute_path = resolve_professional_evidence_path(
        str(root / "professional-intelligence"), run_id, source_id, filename
    )
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)
    sha256 = hashlib.sha256(content).hexdigest()
    entry = validate_professional_artifact_manifest_entry(
        session,
        ProfessionalArtifactManifestEntry(
            capture_run_id=run_id,
            source_id=source_id,
            artifact_type=artifact_type,
            relative_path=str(relative_path),
            sha256=sha256,
            completeness_status=completeness_status,
            retention_days=DEFAULT_RETENTION_DAYS,
        ),
    )
    session.add(
        ProfessionalCaptureArtifact(
            id=str(uuid4()),
            capture_run_id=run_id,
            source_id=source_id,
            artifact_type=entry.artifact_type,
            relative_path=entry.relative_path,
            sha256=entry.sha256,
            completeness_status=entry.completeness_status,
            retention_days=entry.retention_days,
            created_at=utc_now(),
        )
    )


def _capture_source(
    session: Session,
    *,
    root: Path,
    run_id: str,
    source: ProfessionalIntelligenceSource,
    capture_source: CaptureSource,
) -> str:
    captured_at = utc_now()
    try:
        captured = capture_source(source.url)
        completeness = (
            "complete"
            if captured.screenshot_png
            and len(captured.visible_text.strip()) >= 100
            and (captured.http_status is None or 200 <= captured.http_status < 400)
            else "partial"
        )
        rendered_text = {
            "source_id": source.source_id,
            "source_url": source.url,
            "extraction_method": "visible_rendered_dom_text",
            "derived": False,
            "text": captured.visible_text,
        }
        metadata = {
            "source_id": source.source_id,
            "requested_url": source.url,
            "final_url": captured.final_url,
            "title": captured.title,
            "http_status": captured.http_status,
            "captured_at": captured_at.isoformat(),
            "browser_mode": "visible_fresh_context",
            "storage_state_persisted": False,
        }
        diagnostics = {
            "source_id": source.source_id,
            "completeness_status": completeness,
            "errors": [],
        }
        _write_artifact(
            session,
            root=root,
            run_id=run_id,
            source_id=source.source_id,
            artifact_type="screenshot_png",
            filename="page.png",
            content=captured.screenshot_png,
            completeness_status=completeness,
        )
        _write_artifact(
            session,
            root=root,
            run_id=run_id,
            source_id=source.source_id,
            artifact_type="rendered_text_json",
            filename="rendered-text.json",
            content=json.dumps(rendered_text, ensure_ascii=False, indent=2).encode("utf-8"),
            completeness_status=completeness,
        )
        _write_artifact(
            session,
            root=root,
            run_id=run_id,
            source_id=source.source_id,
            artifact_type="capture_metadata_json",
            filename="capture-metadata.json",
            content=json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            completeness_status=completeness,
        )
        _write_artifact(
            session,
            root=root,
            run_id=run_id,
            source_id=source.source_id,
            artifact_type="page_diagnostics_json",
            filename="page-diagnostics.json",
            content=json.dumps(diagnostics, ensure_ascii=False, indent=2).encode("utf-8"),
            completeness_status=completeness,
        )
        return completeness
    except Exception as exc:
        diagnostics = {
            "source_id": source.source_id,
            "completeness_status": "failed",
            "errors": [str(exc)],
            "captured_at": captured_at.isoformat(),
        }
        _write_artifact(
            session,
            root=root,
            run_id=run_id,
            source_id=source.source_id,
            artifact_type="page_diagnostics_json",
            filename="page-diagnostics.json",
            content=json.dumps(diagnostics, ensure_ascii=False, indent=2).encode("utf-8"),
            completeness_status="failed",
        )
        return "failed"


def start_professional_supervised_capture(
    session: Session,
    run_id: str,
    *,
    capture_source: CaptureSource = capture_professional_source_visible,
) -> ProfessionalCaptureRunResponse:
    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise LookupError(f"Professional capture run {run_id} was not found.")
    if effective_capture_run_status(run) != "authorized":
        raise ValueError("A current explicit authorization is required before capture.")
    evidence_root = get_professional_evidence_root(session)
    if not (
        evidence_root.configured
        and evidence_root.root_path
        and evidence_root.exists
        and evidence_root.writable
    ):
        raise ValueError("A verified writable local evidence root is required.")

    sources = [
        ProfessionalIntelligenceSource.model_validate(item)
        for item in json.loads(run.source_snapshot_json)
    ]
    if not sources:
        raise ValueError("The immutable run snapshot contains no sources to capture.")

    run.mode = "supervised_read_only"
    run.status = "running"
    run.started_at = utc_now()
    run.completed_at = None
    run.stop_reason = ""
    session.commit()

    try:
        statuses = [
            _capture_source(
                session,
                root=Path(evidence_root.root_path),
                run_id=run.id,
                source=source,
                capture_source=capture_source,
            )
            for source in sources
        ]
        session.commit()
        run.status = (
            "completed"
            if all(status == "complete" for status in statuses)
            else "completed_with_gaps"
        )
        run.completed_at = utc_now()
        run.stop_reason = (
            "" if run.status == "completed" else "one_or_more_sources_partial_or_failed"
        )
        session.commit()
    except Exception:
        session.rollback()
        run = session.get(ProfessionalCaptureRun, run_id)
        if run is not None:
            run.status = "failed"
            run.completed_at = utc_now()
            run.stop_reason = "capture_engine_failure"
            session.commit()
        raise

    return get_professional_capture_run(session, run.id)
