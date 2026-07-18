"""SQLAlchemy persistence schema."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FormRow(Base):
    __tablename__ = "forms"
    __table_args__ = (
        Index(
            "ix_forms_review_queue_order",
            "review_status",
            "priority",
            "created_at",
            "form_id",
        ),
    )

    form_id: Mapped[str] = mapped_column(String, primary_key=True)
    template_id: Mapped[str] = mapped_column(String, nullable=False)
    template_version: Mapped[str] = mapped_column(String, nullable=False)
    coordinate_version: Mapped[str] = mapped_column(String, nullable=False)
    review_status: Mapped[str] = mapped_column(String, nullable=False)
    export_status: Mapped[str] = mapped_column(String, nullable=False)
    current_record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TemplateVersionRow(Base):
    __tablename__ = "template_versions"
    __table_args__ = (UniqueConstraint("template_key", "version"),)

    version_id: Mapped[str] = mapped_column(String, primary_key=True)
    template_key: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    page: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(String)
    static_elements: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    print_imposition: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class TemplateMetadataRow(Base):
    __tablename__ = "template_metadata"

    template_key: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")


class TemplateFieldRow(Base):
    __tablename__ = "template_fields"
    __table_args__ = (UniqueConstraint("version_id", "field_key"),)

    field_id: Mapped[str] = mapped_column(String, primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("template_versions.version_id"), nullable=False, index=True
    )
    field_key: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


class TemplateArtifactRow(Base):
    __tablename__ = "template_artifacts"

    artifact_id: Mapped[str] = mapped_column(String, primary_key=True)
    version_id: Mapped[str] = mapped_column(
        ForeignKey("template_versions.version_id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    download_name: Mapped[str] = mapped_column(String, nullable=False)
    internal_uri: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)


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


class FormFieldRow(Base):
    __tablename__ = "form_fields"

    field_id: Mapped[str] = mapped_column(String, primary_key=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("forms.form_id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    source_region: Mapped[dict[str, int]] = mapped_column(JSON, nullable=False)
    current_value: Mapped[Any | None] = mapped_column(JSON)
    current_value_source: Mapped[str | None] = mapped_column(String)
    current_record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RecognitionAttemptRow(Base):
    __tablename__ = "recognition_attempts"

    attempt_id: Mapped[str] = mapped_column(String, primary_key=True)
    field_id: Mapped[str] = mapped_column(
        ForeignKey("form_fields.field_id"), nullable=False, index=True
    )
    engine: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    candidate_value: Mapped[Any | None] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    crop_file_id: Mapped[str] = mapped_column(ForeignKey("evidence_files.file_id"), nullable=False)


class EvidenceFileRow(Base):
    __tablename__ = "evidence_files"
    __table_args__ = (
        Index(
            "ux_evidence_files_original_sha256",
            "sha256",
            unique=True,
            sqlite_where=text("type = 'ORIGINAL_IMAGE'"),
        ),
    )

    file_id: Mapped[str] = mapped_column(String, primary_key=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("forms.form_id"), nullable=False, index=True)
    related_field_id: Mapped[str | None] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, nullable=False)
    uri: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
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


class ReviewLeaseRow(Base):
    __tablename__ = "review_leases"

    form_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    lease_token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    forced_release_by: Mapped[str | None] = mapped_column(String)
    forced_release_reason: Mapped[str | None] = mapped_column(String)


class ReviewDraftRow(Base):
    __tablename__ = "review_drafts"

    form_id: Mapped[str] = mapped_column(ForeignKey("forms.form_id"), primary_key=True)
    expected_version: Mapped[int] = mapped_column(Integer, nullable=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    saved_by: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("actor_id", "operation", "resource_id", "idempotency_key"),)

    task_id: Mapped[str] = mapped_column(String, primary_key=True)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    step: Mapped[str | None] = mapped_column(String)
    error: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TaskEventRow(Base):
    __tablename__ = "task_events"
    __table_args__ = (UniqueConstraint("task_id", "sequence"),)

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.task_id"), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    progress: Mapped[int | None] = mapped_column(Integer)
    step: Mapped[str | None] = mapped_column(String)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ExportBatchRow(Base):
    __tablename__ = "export_batches"
    __table_args__ = (
        Index("ux_export_batches_task_id", "task_id", unique=True),
    )

    export_batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    export_type: Mapped[str] = mapped_column(String, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String)
    template_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    mapping_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    mapping_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    included_records: Mapped[list[list[Any]]] = mapped_column(JSON, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    download_name: Mapped[str] = mapped_column(String, nullable=False, default="export.xlsx")
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    exported_by: Mapped[str] = mapped_column(String, nullable=False)
    exported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_batch_id: Mapped[str | None] = mapped_column(String)


class AIReviewRow(Base):
    __tablename__ = "ai_reviews"

    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    form_id: Mapped[str] = mapped_column(ForeignKey("forms.form_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MasterDataRecordRow(Base):
    __tablename__ = "master_data_records"
    __table_args__ = (
        Index(
            "ix_master_data_records_catalog_active_name",
            "catalog",
            "active",
            "display_name",
            "code",
        ),
    )

    catalog: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    updated_by: Mapped[str] = mapped_column(String, nullable=False)


class MasterDataAuditRow(Base):
    __tablename__ = "master_data_audits"
    __table_args__ = (
        Index(
            "ix_master_data_audits_catalog_code_revision",
            "catalog",
            "code",
            "revision",
        ),
    )

    audit_id: Mapped[str] = mapped_column(String, primary_key=True)
    catalog: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String, nullable=False)
