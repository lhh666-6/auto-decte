"""Identity, role and permission value objects."""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    REVIEWER = "REVIEWER"
    FINANCE = "FINANCE"
    AUDITOR = "AUDITOR"


class Permission(StrEnum):
    FORM_READ = "form.read"
    FORM_IMPORT = "form.import"
    FORM_CLASSIFY = "form.classify"
    FORM_TEST_ADMIN = "form.test_admin"
    FORM_EDIT_DRAFT = "form.edit_draft"
    REVIEW_ACQUIRE = "review.acquire"
    REVIEW_CONFIRM = "review.confirm"
    REVIEW_CORRECT = "review.correct"
    REVIEW_RETURN = "review.return"
    REVIEW_VOID = "review.void"
    REVIEW_FORCE_RELEASE = "review.force_release"
    TEMPLATE_READ = "template.read"
    TEMPLATE_CREATE_VERSION = "template.create_version"
    MASTER_DATA_READ = "master_data.read"
    MASTER_DATA_WRITE = "master_data.write"
    EXPORT_PREVIEW = "export.preview"
    EXPORT_CREATE = "export.create"
    EXPORT_DOWNLOAD = "export.download"
    AUDIT_READ = "audit.read"
    EVIDENCE_IMAGE_READ = "evidence.image.read"
    EVIDENCE_AUDIO_READ = "evidence.audio.read"
    TASK_READ = "task.read"
    TASK_CANCEL = "task.cancel"
    TASK_RETRY = "task.retry"


@dataclass(frozen=True, slots=True)
class Actor:
    actor_id: str
    roles: frozenset[Role]
    authenticated: bool = True
    local_full_access: bool = False
