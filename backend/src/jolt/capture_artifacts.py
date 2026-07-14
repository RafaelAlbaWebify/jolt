from __future__ import annotations

import hashlib
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from jolt.database import Base, utc_now


class CaptureArtifact(Base):
    __tablename__ = "capture_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    capture_item_id: Mapped[str] = mapped_column(
        ForeignKey("capture_items.id"), unique=True, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    raw_payload: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)


def stage_capture_artifact(
    session: Session,
    *,
    capture_item_id: str,
    artifact_type: str,
    content_type: str,
    raw_payload: str,
) -> CaptureArtifact:
    artifact = CaptureArtifact(
        id=str(uuid4()),
        capture_item_id=capture_item_id,
        artifact_type=artifact_type,
        content_type=content_type,
        raw_payload=raw_payload,
        content_hash=hashlib.sha256(raw_payload.encode("utf-8")).hexdigest(),
        captured_at=utc_now(),
    )
    session.add(artifact)
    return artifact
