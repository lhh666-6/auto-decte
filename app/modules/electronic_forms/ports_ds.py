"""Repository interfaces for electronic forms persistence."""

from abc import ABC, abstractmethod
from typing import Iterable, Optional

from app.modules.electronic_forms.models_ds import (
    ElectronicDraft,
    ElectronicFormDefinitionVersion,
    ElectronicSubmissionReceipt,
)


class ElectronicFormDefinitionRepository(ABC):
    """Read/write definition versions."""

    @abstractmethod
    def add(self, definition: ElectronicFormDefinitionVersion) -> None: ...

    @abstractmethod
    def get(
        self, definition_version_id: str,
    ) -> ElectronicFormDefinitionVersion | None: ...

    @abstractmethod
    def get_published(
        self, form_type: str,
    ) -> ElectronicFormDefinitionVersion | None: ...

    @abstractmethod
    def list_by_form_type(
        self, form_type: str,
    ) -> list[ElectronicFormDefinitionVersion]: ...


class ElectronicDraftRepository(ABC):
    """Server-side draft persistence with optimistic locking."""

    @abstractmethod
    def add(self, draft: ElectronicDraft) -> None: ...

    @abstractmethod
    def get(self, draft_id: str) -> ElectronicDraft | None: ...

    @abstractmethod
    def list_by_owner(
        self, owner_actor_id: str, device_id: str,
    ) -> list[ElectronicDraft]: ...

    @abstractmethod
    def update(self, draft: ElectronicDraft) -> None: ...

    @abstractmethod
    def delete(self, draft_id: str) -> None: ...


class ElectronicSubmissionReceiptRepository(ABC):
    """Immutable receipt persistence."""

    @abstractmethod
    def add(self, receipt: ElectronicSubmissionReceipt) -> None: ...

    @abstractmethod
    def get(self, receipt_id: str) -> ElectronicSubmissionReceipt | None: ...

    @abstractmethod
    def find_idempotent(
        self,
        actor_id: str,
        device_id: str,
        operation: str,
        client_submission_id: str,
    ) -> ElectronicSubmissionReceipt | None: ...

    @abstractmethod
    def list_by_actor(
        self, actor_id: str, limit: int = 50,
    ) -> list[ElectronicSubmissionReceipt]: ...
