from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from jolt.database import Base


class ProfessionalSourceOverride(Base):
    __tablename__ = "professional_source_overrides"

    source_id: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    initial_scope: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfessionalCaptureRun(Base):
    __tablename__ = "professional_capture_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    mode: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    safety_constraints_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_progress_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    completed_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_source_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    progress_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    authorization_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_present_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stop_reason: Mapped[str] = mapped_column(String(80), nullable=False, default="")


class ProfessionalCaptureArtifact(Base):
    __tablename__ = "professional_capture_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    capture_run_id: Mapped[str] = mapped_column(
        ForeignKey("professional_capture_runs.id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    completeness_status: Mapped[str] = mapped_column(String(20), nullable=False, default="partial")
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProfessionalEvidenceSettings(Base):
    __tablename__ = "professional_evidence_settings"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
