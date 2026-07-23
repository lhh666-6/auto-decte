"""SQLAlchemy persistence schema."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
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
    job_profile_key: Mapped[str | None] = mapped_column(String)
    job_profile_version: Mapped[str | None] = mapped_column(String)
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


class JobProfileVersionRow(Base):
    __tablename__ = "job_profile_versions"
    __table_args__ = (UniqueConstraint("profile_key", "version"),)

    profile_version_id: Mapped[str] = mapped_column(String, primary_key=True)
    profile_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    core_layout: Mapped[str] = mapped_column(String, nullable=False)
    template_version_id: Mapped[str] = mapped_column(
        ForeignKey("template_versions.version_id"), nullable=False, index=True
    )
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    parent_profile_version_id: Mapped[str | None] = mapped_column(String)
    unit: Mapped[str] = mapped_column(String, nullable=False, default="")
    fixed_options: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    pricing_rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    deduction_rules: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    export_mapping: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ReportDefinitionVersionRow(Base):
    __tablename__ = "report_definition_versions"
    __table_args__ = (UniqueConstraint("report_key", "version"),)

    definition_id: Mapped[str] = mapped_column(String, primary_key=True)
    report_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)


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
    __table_args__ = (Index("ux_export_batches_task_id", "task_id", unique=True),)

    export_batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    export_type: Mapped[str] = mapped_column(String, nullable=False)
    task_id: Mapped[str | None] = mapped_column(String)
    template_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
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


# ── Electronic forms (mobile / PWA) ────────────────────────────


class ElectronicFormDefinitionVersionRow(Base):
    __tablename__ = "electronic_form_definition_versions"
    __table_args__ = (
        UniqueConstraint("form_type", "version"),
        Index("ix_ef_def_versions_form_type_status", "form_type", "status"),
    )

    definition_version_id: Mapped[str] = mapped_column(String, primary_key=True)
    form_type: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    template_version_id: Mapped[str | None] = mapped_column(String)
    job_profile_version_id: Mapped[str | None] = mapped_column(String)
    presentation_config: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ElectronicDraftRow(Base):
    __tablename__ = "electronic_drafts"

    draft_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_actor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    subject_employee_code: Mapped[str] = mapped_column(String, nullable=False)
    device_id: Mapped[str] = mapped_column(String, nullable=False)
    definition_version_id: Mapped[str] = mapped_column(String, nullable=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ElectronicSubmissionReceiptRow(Base):
    __tablename__ = "electronic_submission_receipts"
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "device_id",
            "operation",
            "client_submission_id",
            name="ux_electronic_receipts_idempotency",
        ),
        Index("ix_es_receipts_actor_submitted", "actor_id", "submitted_at"),
    )

    receipt_id: Mapped[str] = mapped_column(String, primary_key=True)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    subject_employee_code: Mapped[str] = mapped_column(String, nullable=False)
    device_id: Mapped[str] = mapped_column(String, nullable=False)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    client_submission_id: Mapped[str] = mapped_column(String, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    form_id: Mapped[str | None] = mapped_column(String)
    record_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FactRecordRow(Base):
    __tablename__ = "fact_records"
    __table_args__ = (
        Index("ix_fact_records_employee_date", "subject_employee_code", "production_date"),
        Index("ix_fact_records_review_status", "review_status"),
        Index("ix_fact_records_export_status", "export_status"),
        Index("ix_fact_records_source", "source_submission_id"),
    )

    fact_record_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_submission_id: Mapped[str | None] = mapped_column(String)
    source_form_id: Mapped[str | None] = mapped_column(String)
    subject_employee_code: Mapped[str] = mapped_column(String, nullable=False)
    subject_employee_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    workshop: Mapped[str] = mapped_column(String, nullable=False, default="")
    work_order_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    product_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    process_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    production_date: Mapped[str] = mapped_column(String, nullable=False, default="")
    shift: Mapped[str] = mapped_column(String, nullable=False, default="")
    blocks_completed: Mapped[int | None] = mapped_column(Integer)
    pieces_per_block: Mapped[int | None] = mapped_column(Integer)
    total_pieces: Mapped[int | None] = mapped_column(Integer)
    measurement_values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    anomalies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    corrections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    review_status: Mapped[str] = mapped_column(String, nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String, nullable=False, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    export_status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MobileCredentialRow(Base):
    __tablename__ = "mobile_credentials"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_catalog", "employee_code"],
            ["master_data_records.catalog", "master_data_records.code"],
        ),
    )

    employee_catalog: Mapped[str] = mapped_column(String, primary_key=True)
    employee_code: Mapped[str] = mapped_column(String, primary_key=True)
    pin_salt: Mapped[str] = mapped_column(String, nullable=False)
    pin_hash: Mapped[str] = mapped_column(String, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MobileAccessProfileRow(Base):
    __tablename__ = "mobile_access_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_catalog", "employee_code"],
            ["master_data_records.catalog", "master_data_records.code"],
        ),
    )

    employee_catalog: Mapped[str] = mapped_column(String, primary_key=True)
    employee_code: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    team_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    position: Mapped[str] = mapped_column(String, nullable=False, default="")
    roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_form_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    allowed_processes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    factory_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    factory_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MobileSessionRow(Base):
    __tablename__ = "mobile_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_catalog", "employee_code"],
            ["master_data_records.catalog", "master_data_records.code"],
        ),
        Index("ix_mobile_sessions_employee", "employee_catalog", "employee_code"),
    )

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_catalog: Mapped[str] = mapped_column(String, nullable=False)
    employee_code: Mapped[str] = mapped_column(String, nullable=False)
    device_id: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ── Bamboo production workflow ─────────────────────────────────


class BambooFactoryRow(Base):
    __tablename__ = "bamboo_factories"

    factory_id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooRoleDefinitionRow(Base):
    __tablename__ = "bamboo_role_definitions"

    role_code: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    self_requestable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EmployeeBambooAssignmentRow(Base):
    __tablename__ = "employee_bamboo_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_catalog", "employee_code"],
            ["master_data_records.catalog", "master_data_records.code"],
        ),
        Index(
            "ix_employee_bamboo_assignment_current",
            "employee_catalog",
            "employee_code",
            "status",
            "effective_at",
        ),
    )

    assignment_id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_catalog: Mapped[str] = mapped_column(String, nullable=False)
    employee_code: Mapped[str] = mapped_column(String, nullable=False)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    role_code: Mapped[str] = mapped_column(
        ForeignKey("bamboo_role_definitions.role_code"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooRecordRow(Base):
    __tablename__ = "bamboo_records"
    __table_args__ = (
        Index(
            "ix_bamboo_records_factory_stage",
            "factory_id",
            "current_stage",
            "status",
            "updated_at",
        ),
        Index(
            "ix_bamboo_records_source_lookup",
            "form_type",
            "source_record_id",
            unique=True,
        ),
        Index(
            "ux_bamboo_records_mobile_create_idempotency",
            "created_by",
            "source_type",
            "source_ref",
            unique=True,
            sqlite_where=text(
                "source_type = 'MOBILE_CREATED' "
                "AND source_ref IS NOT NULL AND source_ref <> ''"
            ),
            postgresql_where=text(
                "source_type = 'MOBILE_CREATED' "
                "AND source_ref IS NOT NULL AND source_ref <> ''"
            ),
        ),
    )

    record_id: Mapped[str] = mapped_column(String, primary_key=True)
    display_no: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String)
    form_type: Mapped[str] = mapped_column(String, nullable=False, default="SORTING")
    production_object_id: Mapped[str | None] = mapped_column(String)
    source_record_id: Mapped[str | None] = mapped_column(
        ForeignKey("bamboo_records.record_id")
    )
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    base_info: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    current_stage: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooStageSubmissionRow(Base):
    __tablename__ = "bamboo_stage_submissions"
    __table_args__ = (
        UniqueConstraint(
            "record_id",
            "stage_key",
            "version",
            name="ux_bamboo_stage_version",
        ),
        Index(
            "ix_bamboo_stage_submissions_record_stage",
            "record_id",
            "stage_key",
            "version",
        ),
    )

    submission_id: Mapped[str] = mapped_column(String, primary_key=True)
    record_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_records.record_id", ondelete="CASCADE"), nullable=False
    )
    stage_key: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    values: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_name: Mapped[str] = mapped_column(String, nullable=False)
    role_code: Mapped[str] = mapped_column(String, nullable=False)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invalidated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BambooCageOccupancyRow(Base):
    __tablename__ = "bamboo_cage_occupancies"
    __table_args__ = (
        Index(
            "ux_bamboo_cage_occupancy_active",
            "factory_id",
            "cage_no_key",
            unique=True,
            sqlite_where=text("released_at IS NULL"),
            postgresql_where=text("released_at IS NULL"),
        ),
    )

    occupancy_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    cage_no: Mapped[str] = mapped_column(String, nullable=False)
    cage_no_key: Mapped[str] = mapped_column(String, nullable=False)
    sorting_record_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_records.record_id"), nullable=False, unique=True
    )
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_by_submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("bamboo_stage_submissions.submission_id")
    )


class BambooSignatureRow(Base):
    __tablename__ = "bamboo_signatures"
    __table_args__ = (
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="ux_bamboo_signature_idempotency",
        ),
    )

    signature_id: Mapped[str] = mapped_column(String, primary_key=True)
    submission_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_stage_submissions.submission_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    employee_code: Mapped[str] = mapped_column(String, nullable=False)
    actor_name: Mapped[str] = mapped_column(String, nullable=False)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    role_code: Mapped[str] = mapped_column(String, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    device_id: Mapped[str] = mapped_column(String, nullable=False)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)


class BambooPayrollRuleVersionRow(Base):
    __tablename__ = "bamboo_payroll_rule_versions"
    __table_args__ = (
        UniqueConstraint(
            "rule_key", "factory_id", "version", name="ux_bamboo_payroll_rule_version"
        ),
        Index("ix_bamboo_payroll_rule_current", "rule_key", "factory_id", "active", "effective_at"),
    )

    rule_version_id: Mapped[str] = mapped_column(String, primary_key=True)
    rule_key: Mapped[str] = mapped_column(String, nullable=False)
    factory_id: Mapped[str | None] = mapped_column(ForeignKey("bamboo_factories.factory_id"))
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooPayrollFactRow(Base):
    __tablename__ = "bamboo_payroll_facts"
    __table_args__ = (
        UniqueConstraint(
            "record_id", "fact_type", "version", name="ux_bamboo_payroll_fact_version"
        ),
        Index("ix_bamboo_payroll_fact_status", "record_id", "status", "fact_type"),
    )

    fact_id: Mapped[str] = mapped_column(String, primary_key=True)
    record_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_records.record_id", ondelete="CASCADE"), nullable=False
    )
    fact_type: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    rule_version_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_payroll_rule_versions.rule_version_id"), nullable=False
    )
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    allocations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    total_amount: Mapped[str] = mapped_column(String, nullable=False)
    source_submission_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BambooInspectionRow(Base):
    __tablename__ = "bamboo_inspections"
    __table_args__ = (
        UniqueConstraint("record_id", "serial_no", name="ux_bamboo_inspection_serial"),
        UniqueConstraint("actor_id", "idempotency_key", name="ux_bamboo_inspection_idempotency"),
        Index("ix_bamboo_inspection_record", "record_id", "signed_at"),
        Index(
            "ux_bamboo_inspection_formal_record",
            "record_id",
            unique=True,
            sqlite_where=text("inspection_kind = 'FORMAL'"),
            postgresql_where=text("inspection_kind = 'FORMAL'"),
        ),
    )

    inspection_id: Mapped[str] = mapped_column(String, primary_key=True)
    record_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_records.record_id", ondelete="CASCADE"), nullable=False
    )
    serial_no: Mapped[str] = mapped_column(String, nullable=False)
    target_stage: Mapped[str] = mapped_column(String, nullable=False)
    moisture_points: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    average_value: Mapped[str] = mapped_column(String, nullable=False)
    conclusion: Mapped[str] = mapped_column(String, nullable=False)
    note: Mapped[str | None] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_name: Mapped[str] = mapped_column(String, nullable=False)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    role_code: Mapped[str] = mapped_column(String, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    device_id: Mapped[str] = mapped_column(String, nullable=False)
    request_id: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    window_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    inspection_kind: Mapped[str] = mapped_column(String, nullable=False, default="FORMAL")


class BambooInspectionWindowRow(Base):
    __tablename__ = "bamboo_inspection_windows"
    __table_args__ = (
        Index(
            "ix_bamboo_inspection_window_queue",
            "factory_id",
            "status",
            "deadline_at",
        ),
    )

    record_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_records.record_id", ondelete="CASCADE"), primary_key=True
    )
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    claimed_by: Mapped[str | None] = mapped_column(String)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inspection_id: Mapped[str | None] = mapped_column(
        ForeignKey("bamboo_inspections.inspection_id")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminated_by: Mapped[str | None] = mapped_column(String)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appeal_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appeal_claimed_by: Mapped[str | None] = mapped_column(String)
    appeal_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appeal_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    appeal_submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    appeal_decision: Mapped[str | None] = mapped_column(String)
    appeal_decision_note: Mapped[str | None] = mapped_column(String)
    appeal_decided_by: Mapped[str | None] = mapped_column(String)
    appeal_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class MobileNotificationRow(Base):
    __tablename__ = "mobile_notifications"
    __table_args__ = (
        Index(
            "ix_mobile_notification_inbox",
            "recipient_actor_id",
            "read_at",
            "created_at",
        ),
    )

    notification_id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient_actor_id: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    link: Mapped[str | None] = mapped_column(String)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooEvidenceAssetRow(Base):
    __tablename__ = "bamboo_evidence_assets"

    asset_id: Mapped[str] = mapped_column(String, primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_inspections.inspection_id", ondelete="CASCADE"), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String, nullable=False)
    file_id: Mapped[str | None] = mapped_column(String)
    uri: Mapped[str | None] = mapped_column(String)
    mime_type: Mapped[str | None] = mapped_column(String)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    text_content: Mapped[str | None] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooInspectionExceptionRow(Base):
    __tablename__ = "bamboo_inspection_exceptions"

    exception_id: Mapped[str] = mapped_column(String, primary_key=True)
    inspection_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_inspections.inspection_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    record_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_records.record_id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    resolution: Mapped[str | None] = mapped_column(String)
    closed_by: Mapped[str | None] = mapped_column(String)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class BambooReturnRow(Base):
    __tablename__ = "bamboo_returns"

    return_id: Mapped[str] = mapped_column(String, primary_key=True)
    record_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_records.record_id", ondelete="CASCADE"), nullable=False
    )
    requested_by: Mapped[str] = mapped_column(String, nullable=False)
    requested_role: Mapped[str] = mapped_column(String, nullable=False)
    target_stages: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_revision: Mapped[int] = mapped_column(Integer, nullable=False)


class BambooPlantAuditRow(Base):
    __tablename__ = "bamboo_plant_audits"

    audit_id: Mapped[str] = mapped_column(String, primary_key=True)
    record_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_records.record_id", ondelete="CASCADE"), nullable=False
    )
    submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("bamboo_stage_submissions.submission_id")
    )
    earliest_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    audited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[str | None] = mapped_column(String)
    result: Mapped[str] = mapped_column(String, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class BambooRoleChangeRequestRow(Base):
    __tablename__ = "bamboo_role_change_requests"
    __table_args__ = (
        Index("ix_bamboo_role_change_pending", "factory_id", "status", "requested_at"),
    )

    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_code: Mapped[str] = mapped_column(String, nullable=False)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    from_role: Mapped[str] = mapped_column(String, nullable=False)
    to_role: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    requested_by: Mapped[str] = mapped_column(String, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class BambooPersonnelTransferRow(Base):
    __tablename__ = "bamboo_personnel_transfers"
    __table_args__ = (
        Index(
            "ix_bamboo_personnel_transfer_queue",
            "status",
            "source_factory_id",
            "target_factory_id",
            "requested_at",
        ),
    )

    transfer_id: Mapped[str] = mapped_column(String, primary_key=True)
    employee_code: Mapped[str] = mapped_column(String, nullable=False)
    transfer_type: Mapped[str] = mapped_column(String, nullable=False)
    source_factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    target_factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    from_role: Mapped[str] = mapped_column(String, nullable=False)
    to_role: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    requested_by: Mapped[str] = mapped_column(String, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_manager_id: Mapped[str | None] = mapped_column(String)
    source_manager_decision: Mapped[str | None] = mapped_column(String)
    source_manager_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_manager_id: Mapped[str | None] = mapped_column(String)
    target_manager_decision: Mapped[str | None] = mapped_column(String)
    target_manager_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admin_id: Mapped[str | None] = mapped_column(String)
    admin_decision: Mapped[str | None] = mapped_column(String)
    admin_note: Mapped[str | None] = mapped_column(String)
    admin_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class BambooDailyExportBatchRow(Base):
    __tablename__ = "bamboo_daily_export_batches"
    __table_args__ = (
        UniqueConstraint(
            "factory_id", "business_date", "version", name="ux_bamboo_daily_batch_version"
        ),
    )

    batch_id: Mapped[str] = mapped_column(String, primary_key=True)
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    business_date: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    supplemental: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("bamboo_daily_export_batches.batch_id")
    )
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooDailyExportItemRow(Base):
    __tablename__ = "bamboo_daily_export_items"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "payroll_fact_id", "employee_code", name="ux_bamboo_daily_fact_employee"
        ),
        Index("ix_bamboo_daily_item_status", "batch_id", "status"),
    )

    item_id: Mapped[str] = mapped_column(String, primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_daily_export_batches.batch_id", ondelete="CASCADE"), nullable=False
    )
    payroll_fact_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_payroll_facts.fact_id"), nullable=False
    )
    record_id: Mapped[str] = mapped_column(ForeignKey("bamboo_records.record_id"), nullable=False)
    employee_code: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    decision_by: Mapped[str | None] = mapped_column(String)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String)
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class BambooFinanceInquiryRow(Base):
    __tablename__ = "bamboo_finance_inquiries"

    inquiry_id: Mapped[str] = mapped_column(String, primary_key=True)
    item_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_daily_export_items.item_id"), nullable=False
    )
    factory_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_factories.factory_id"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooFinanceInquiryMessageRow(Base):
    __tablename__ = "bamboo_finance_inquiry_messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    inquiry_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_finance_inquiries.inquiry_id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_name: Mapped[str] = mapped_column(String, nullable=False)
    role_code: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BambooCorrectionCaseRow(Base):
    __tablename__ = "bamboo_correction_cases"

    case_id: Mapped[str] = mapped_column(String, primary_key=True)
    item_id: Mapped[str] = mapped_column(
        ForeignKey("bamboo_daily_export_items.item_id"), nullable=False
    )
    record_id: Mapped[str] = mapped_column(ForeignKey("bamboo_records.record_id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supplement_batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("bamboo_daily_export_batches.batch_id")
    )
