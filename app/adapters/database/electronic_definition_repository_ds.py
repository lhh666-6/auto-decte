"""Engine-scoped repository for electronic definition versions."""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.electronic_forms_repository_ds import (
    _definition_from_row,
    _presentation_config_to_dict,
)
from app.adapters.database.models import ElectronicFormDefinitionVersionRow
from app.modules.electronic_forms.models_ds import (
    DefinitionStatus,
    ElectronicFormDefinitionVersion,
)
from app.modules.electronic_forms.ports_ds import ElectronicFormDefinitionRepository


class SqlAlchemyElectronicDefinitionRepository(ElectronicFormDefinitionRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, definition: ElectronicFormDefinitionVersion) -> None:
        with Session(self._engine) as session, session.begin():
            session.merge(
                ElectronicFormDefinitionVersionRow(
                    definition_version_id=definition.definition_version_id,
                    form_type=definition.form_type,
                    version=definition.version,
                    status=definition.status.value,
                    display_name=definition.display_name,
                    template_version_id=definition.template_version_id,
                    job_profile_version_id=definition.job_profile_version_id,
                    presentation_config=_presentation_config_to_dict(
                        definition.presentation_config
                    ),
                    created_by=definition.created_by,
                    created_at=definition.created_at,
                    published_at=definition.published_at,
                )
            )

    def get(self, definition_version_id: str) -> ElectronicFormDefinitionVersion | None:
        with Session(self._engine) as session:
            row = session.get(ElectronicFormDefinitionVersionRow, definition_version_id)
            return _definition_from_row(row) if row is not None else None

    def get_published(self, form_type: str) -> ElectronicFormDefinitionVersion | None:
        statement = (
            select(ElectronicFormDefinitionVersionRow)
            .where(
                ElectronicFormDefinitionVersionRow.form_type == form_type,
                ElectronicFormDefinitionVersionRow.status == DefinitionStatus.PUBLISHED.value,
            )
            .order_by(ElectronicFormDefinitionVersionRow.version.desc())
            .limit(1)
        )
        with Session(self._engine) as session:
            row = session.scalar(statement)
            return _definition_from_row(row) if row is not None else None

    def list_by_form_type(self, form_type: str) -> list[ElectronicFormDefinitionVersion]:
        statement = (
            select(ElectronicFormDefinitionVersionRow)
            .where(ElectronicFormDefinitionVersionRow.form_type == form_type)
            .order_by(ElectronicFormDefinitionVersionRow.version.desc())
        )
        with Session(self._engine) as session:
            return [_definition_from_row(row) for row in session.scalars(statement)]
