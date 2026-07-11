"""SQLAlchemy persistence schema."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FormRow(Base):
    __tablename__ = "forms"

    form_id: Mapped[str] = mapped_column(String, primary_key=True)
    template_id: Mapped[str] = mapped_column(String, nullable=False)
    template_version: Mapped[str] = mapped_column(String, nullable=False)
    coordinate_version: Mapped[str] = mapped_column(String, nullable=False)
    review_status: Mapped[str] = mapped_column(String, nullable=False)
    export_status: Mapped[str] = mapped_column(String, nullable=False)
    current_record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RecordVersionRow(Base):
    __tablename__ = "record_versions"
    __table_args__ = (UniqueConstraint("form_id", "version"),)

    record_id: Mapped[str] = mapped_column(String, primary_key=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("forms.form_id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, nullable=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str] = mapped_column(String, nullable=False, default="")
    confirmed_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceFileRow(Base):
    __tablename__ = "evidence_files"

    file_id: Mapped[str] = mapped_column(String, primary_key=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("forms.form_id"), nullable=False, index=True)
    related_field_id: Mapped[str | None] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    immutable: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEventRow(Base):
    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("forms.form_id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(String)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class ExportBatchRow(Base):
    __tablename__ = "export_batches"

    export_batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    export_type: Mapped[str] = mapped_column(String, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    included_records: Mapped[list[list[Any]]] = mapped_column(JSON, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    exported_by: Mapped[str] = mapped_column(String, nullable=False)
    exported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_batch_id: Mapped[str | None] = mapped_column(String)
