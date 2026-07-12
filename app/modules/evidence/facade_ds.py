"""Evidence management module facade."""

from pathlib import Path

from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.import_forms import AudioTrigger, ImportForms
from app.application.ports import AuditRepository
from app.domain.models import EvidenceFile, EvidenceType


class EvidenceFacade:
    """Evidence management boundary backed by the import service and repository."""

    def __init__(
        self,
        repository: SqlAlchemyFormRepository,
        storage: LocalEvidenceStorage,
        audits: AuditRepository,
    ) -> None:
        self._importer = ImportForms(
            forms=repository,
            evidence=repository,
            audits=audits,
            storage=storage,
        )
        self._repository = repository

    def import_image(
        self,
        source: Path,
        form_id: str,
        template_id: str,
        template_version: str,
        actor_id: str,
    ) -> EvidenceFile:
        """Import a form image and register the form."""
        return self._importer.import_image(source, form_id, template_id, template_version, actor_id)

    def import_audio(
        self,
        source: Path,
        form_id: str,
        actor_id: str,
        trigger: AudioTrigger,
        related_field_id: str | None = None,
    ) -> EvidenceFile:
        """Import an audio evidence file for an existing form."""
        return self._importer.import_audio(source, form_id, actor_id, trigger, related_field_id)

    def list_evidence(self, form_id: str) -> list[EvidenceFile]:
        """List all evidence files for a given form."""
        return self._repository.list_evidence(form_id)

    def find_by_sha256(self, sha256: str) -> EvidenceFile | None:
        """Look up an evidence file by its content hash."""
        return self._repository.find_by_sha256(sha256)

    def add_evidence(
        self,
        form_id: str,
        evidence_type: EvidenceType,
        uri: str,
        sha256: str,
        related_field_id: str | None = None,
    ) -> EvidenceFile:
        """Register an already-stored evidence file without importing."""
        from uuid import uuid4

        item = EvidenceFile(
            file_id=f"FILE-{uuid4().hex}",
            form_id=form_id,
            type=evidence_type,
            uri=uri,
            sha256=sha256,
            related_field_id=related_field_id,
        )
        self._repository.add_evidence(item)
        return item
