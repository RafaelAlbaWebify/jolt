from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.professional_intelligence_capture_runs import get_professional_capture_run
from jolt.professional_intelligence_evidence_root import get_professional_evidence_root
from jolt.professional_intelligence_records import (
    ProfessionalCaptureArtifact,
    ProfessionalCaptureRun,
)

DELETE_CAPTURE_CONFIRMATION_PHRASE = "DELETE CAPTURE RUN"


class ProfessionalCaptureDeletionRequest(BaseModel):
    confirmation_phrase: str


class ProfessionalCaptureDeletionResult(BaseModel):
    run_id: str
    deleted_artifact_count: int
    deleted_evidence_directory: bool


def delete_professional_capture_run(
    session: Session,
    run_id: str,
    request: ProfessionalCaptureDeletionRequest,
) -> ProfessionalCaptureDeletionResult:
    if request.confirmation_phrase != DELETE_CAPTURE_CONFIRMATION_PHRASE:
        raise ValueError("The exact deletion confirmation phrase is required.")

    run = session.get(ProfessionalCaptureRun, run_id)
    if run is None:
        raise LookupError(f"Professional capture run {run_id} was not found.")
    if run.status == "running":
        raise ValueError("A running capture must be cancelled before it can be deleted.")

    # Resolve the effective status first so expired authorizations are still deletable.
    get_professional_capture_run(session, run_id)
    artifacts = session.scalars(
        select(ProfessionalCaptureArtifact).where(
            ProfessionalCaptureArtifact.capture_run_id == run_id
        )
    ).all()

    evidence_root = get_professional_evidence_root(session)
    deleted_evidence_directory = False
    if evidence_root.root_path:
        root = Path(evidence_root.root_path).resolve(strict=False)
        professional_root = (root / "professional-intelligence").resolve(strict=False)
        run_directory = (professional_root / run_id).resolve(strict=False)
        try:
            run_directory.relative_to(professional_root)
        except ValueError as exc:
            raise ValueError(
                "Capture evidence must remain contained under the Professional evidence root."
            ) from exc
        if run_directory.exists():
            shutil.rmtree(run_directory)
            deleted_evidence_directory = True

    for artifact in artifacts:
        session.delete(artifact)
    session.delete(run)
    session.commit()

    return ProfessionalCaptureDeletionResult(
        run_id=run_id,
        deleted_artifact_count=len(artifacts),
        deleted_evidence_directory=deleted_evidence_directory,
    )
