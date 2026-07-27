from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import utc_now
from jolt.professional_intelligence_capture_runs import (
    ProfessionalCaptureRunResponse,
    ProfessionalSourceProgress,
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
    readiness_status: str = "fixture_provided"
    readiness_detail: str = "Capture source supplied ready content."


@dataclass(frozen=True)
class StagedProfessionalArtifact:
    staged_path: Path
    final_path: Path


CaptureSource = Callable[[str], CapturedProfessionalPage]


def capture_professional_source_visible(url: str) -> CapturedProfessionalPage:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        try:
            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            network_idle = True
            try:
                page.wait_for_load_state("networkidle", timeout=5_000)
            except PlaywrightTimeoutError:
                network_idle = False

            visible_text = ""
            for _ in range(40):
                visible_text = page.locator("body").inner_text(timeout=2_000)
                if len(visible_text.strip()) >= 100:
                    break
                page.wait_for_timeout(250)

            body_ready = len(visible_text.strip()) >= 100
            if network_idle and body_ready:
                readiness_status = "network_idle_and_body_ready"
                readiness_detail = "Network became idle and rendered body text reached the threshold."
            elif body_ready:
                readiness_status = "body_ready"
                readiness_detail = "Rendered body text reached the threshold before network idle."
            else:
                readiness_status = "readiness_timeout"
                readiness_detail = "Rendered body text did not reach the readiness threshold."

            return CapturedProfessionalPage(
                screenshot_png=page.screenshot(full_page=True),
                visible_text=visible_text,
                title=page.title(),
                final_url=page.url,
                http_status=response.status if response is not None else None,
                readiness_status=readiness_status,
                readiness_detail=readiness_detail,
            )
        finally:
            context.close()
            browser.close()


def _staged_path(final_path: Path) -> Path:
    return final_path.with_name(f"{final_path.name}.staged")


def _manifest_paths(session: Session, root: Path) -> dict[Path, ProfessionalCaptureArtifact]:
    artifacts = session.scalars(select(ProfessionalCaptureArtifact)).all()
    professional_root = (root / "professional-intelligence").resolve()
    paths: dict[Path, ProfessionalCaptureArtifact] = {}
    for artifact in artifacts:
        relative = PurePosixPath(artifact.relative_path)
        if not relative.parts or relative.parts[0] != "professional-intelligence":
            continue
        final_path = (root / Path(*relative.parts)).resolve()
        if not final_path.is_relative_to(professional_root):
            continue
        paths[final_path] = artifact
    return paths


def reconcile_professional_capture_artifacts(session: Session, root: Path) -> None:
    professional_root = (root / "professional-intelligence").resolve()
    professional_root.mkdir(parents=True, exist_ok=True)
    manifest_paths = _manifest_paths(session, root)

    for final_path in manifest_paths:
        staged_path = _staged_path(final_path)
        if final_path.exists():
            staged_path.unlink(missing_ok=True)
        elif staged_path.exists():
            final_path.parent.mkdir(parents=True, exist_ok=True)
            staged_path.replace(final_path)

    for path in sorted(professional_root.rglob("*"), reverse=True):
        if path.is_dir():
            with suppress(OSError):
                path.rmdir()
            continue
        final_path = (
            path.with_name(path.name.removesuffix(".staged"))
            if path.name.endswith(".staged")
            else path
        )
        if final_path not in manifest_paths:
            path.unlink(missing_ok=True)


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
) -> StagedProfessionalArtifact:
    relative_path = PurePosixPath("professional-intelligence", run_id, source_id, filename)
    final_path = resolve_professional_evidence_path(
        str(root / "professional-intelligence"), run_id, source_id, filename
    )
    staged_path = _staged_path(final_path)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_bytes(content)
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
    return StagedProfessionalArtifact(staged_path=staged_path, final_path=final_path)


def _capture_source(
    session: Session,
    *,
    root: Path,
    run_id: str,
    source: ProfessionalIntelligenceSource,
    capture_source: CaptureSource,
    staged_artifacts: list[StagedProfessionalArtifact],
) -> str:
    captured_at = utc_now()
    try:
        captured = capture_source(source.url)
        completeness = (
            "complete"
            if captured.screenshot_png
            and len(captured.visible_text.strip()) >= 100
            and captured.readiness_status != "readiness_timeout"
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
            "readiness_status": captured.readiness_status,
            "readiness_detail": captured.readiness_detail,
        }
        diagnostics = {
            "source_id": source.source_id,
            "completeness_status": completeness,
            "readiness_status": captured.readiness_status,
            "errors": [],
        }
        for artifact_type, filename, content in (
            ("screenshot_png", "page.png", captured.screenshot_png),
            (
                "rendered_text_json",
                "rendered-text.json",
                json.dumps(rendered_text, ensure_ascii=False, indent=2).encode("utf-8"),
            ),
            (
                "capture_metadata_json",
                "capture-metadata.json",
                json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8"),
            ),
            (
                "page_diagnostics_json",
                "page-diagnostics.json",
                json.dumps(diagnostics, ensure_ascii=False, indent=2).encode("utf-8"),
            ),
        ):
            staged_artifacts.append(
                _write_artifact(
                    session,
                    root=root,
                    run_id=run_id,
                    source_id=source.source_id,
                    artifact_type=artifact_type,
                    filename=filename,
                    content=content,
                    completeness_status=completeness,
                )
            )
        return completeness
    except Exception as exc:
        diagnostics = {
            "source_id": source.source_id,
            "completeness_status": "failed",
            "errors": [str(exc)],
            "captured_at": captured_at.isoformat(),
        }
        staged_artifacts.append(
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
        )
        return "failed"


def _finalize_staged_artifacts(staged_artifacts: list[StagedProfessionalArtifact]) -> None:
    for artifact in staged_artifacts:
        artifact.final_path.parent.mkdir(parents=True, exist_ok=True)
        artifact.staged_path.replace(artifact.final_path)


def _discard_staged_artifacts(staged_artifacts: list[StagedProfessionalArtifact]) -> None:
    for artifact in staged_artifacts:
        artifact.staged_path.unlink(missing_ok=True)


def _load_progress(run: ProfessionalCaptureRun) -> list[ProfessionalSourceProgress]:
    return [
        ProfessionalSourceProgress.model_validate(item)
        for item in json.loads(run.source_progress_json or "[]")
    ]


def _save_progress(run: ProfessionalCaptureRun, progress: list[ProfessionalSourceProgress]) -> None:
    run.source_progress_json = json.dumps(
        [item.model_dump(mode="json") for item in progress]
    )
    run.progress_updated_at = utc_now()


def _update_source_progress(
    progress: list[ProfessionalSourceProgress],
    source_id: str,
    **changes: object,
) -> None:
    for index, item in enumerate(progress):
        if item.source_id == source_id:
            progress[index] = item.model_copy(update=changes)
            return
    raise LookupError(f"Source progress for {source_id} was not found.")


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

    root = Path(evidence_root.root_path)
    reconcile_professional_capture_artifacts(session, root)
    sources = [
        ProfessionalIntelligenceSource.model_validate(item)
        for item in json.loads(run.source_snapshot_json)
    ]
    if not sources:
        raise ValueError("The immutable run snapshot contains no sources to capture.")

    progress = _load_progress(run)
    if not progress:
        progress = [
            ProfessionalSourceProgress(source_id=source.source_id, status="pending")
            for source in sources
        ]

    run.mode = "supervised_read_only"
    run.status = "running"
    run.started_at = utc_now()
    run.completed_at = None
    run.stop_reason = ""
    run.cancel_requested = False
    run.completed_source_count = 0
    run.current_source_id = ""
    _save_progress(run, progress)
    session.commit()

    statuses: list[str] = []
    try:
        for source in sources:
            session.expire_all()
            run = session.get(ProfessionalCaptureRun, run_id)
            if run is None:
                raise LookupError(f"Professional capture run {run_id} was not found.")
            progress = _load_progress(run)
            if run.cancel_requested:
                run.status = "cancelled"
                run.completed_at = utc_now()
                run.current_source_id = ""
                run.stop_reason = "cancelled_by_user"
                for item in progress:
                    if item.status == "pending":
                        _update_source_progress(
                            progress,
                            item.source_id,
                            status="skipped",
                            detail="Skipped because cancellation was requested.",
                        )
                _save_progress(run, progress)
                session.commit()
                return get_professional_capture_run(session, run.id)

            started_at = utc_now()
            run.current_source_id = source.source_id
            _update_source_progress(
                progress,
                source.source_id,
                status="running",
                started_at=started_at,
                detail="Visible supervised capture started.",
            )
            _save_progress(run, progress)
            session.commit()

            staged_artifacts: list[StagedProfessionalArtifact] = []
            manifests_committed = False
            try:
                status = _capture_source(
                    session,
                    root=root,
                    run_id=run.id,
                    source=source,
                    capture_source=capture_source,
                    staged_artifacts=staged_artifacts,
                )
                statuses.append(status)
                completed_at = utc_now()
                progress = _load_progress(run)
                _update_source_progress(
                    progress,
                    source.source_id,
                    status="completed" if status != "failed" else "failed",
                    completed_at=completed_at,
                    completeness_status=status,
                    detail=f"Source capture finished with {status} completeness.",
                )
                run.completed_source_count += 1
                run.current_source_id = ""
                _save_progress(run, progress)
                session.commit()
                manifests_committed = True
                _finalize_staged_artifacts(staged_artifacts)
            except Exception:
                session.rollback()
                if not manifests_committed:
                    _discard_staged_artifacts(staged_artifacts)
                raise

        run = session.get(ProfessionalCaptureRun, run_id)
        if run is None:
            raise LookupError(f"Professional capture run {run_id} was not found.")
        run.status = (
            "completed"
            if all(status == "complete" for status in statuses)
            else "completed_with_gaps"
        )
        run.completed_at = utc_now()
        run.current_source_id = ""
        run.stop_reason = (
            "" if run.status == "completed" else "one_or_more_sources_partial_or_failed"
        )
        run.progress_updated_at = run.completed_at
        session.commit()
    except Exception:
        session.rollback()
        run = session.get(ProfessionalCaptureRun, run_id)
        if run is not None:
            run.status = "failed"
            run.completed_at = utc_now()
            run.current_source_id = ""
            run.progress_updated_at = run.completed_at
            run.stop_reason = "capture_engine_failure"
            session.commit()
        raise

    return get_professional_capture_run(session, run.id)
