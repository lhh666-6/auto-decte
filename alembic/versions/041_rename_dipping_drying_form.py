"""041_rename_dipping_drying_form

V1 Business Form Name Update:
《配片数计量考核表》 → 《竹丝浸胶干燥生产记录表》

Updates existing ManagedFormDefinitionRow.name for DIPPING_DRYING.
Does NOT modify: definition_id, version_id, form_key, schema_json,
content_hash, activation status, or production record provenance.

Revision ID: 041_rename_dipping_drying_form
Revises: 040_quality_signature
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers
revision: str = "041_rename_dipping_drying_form"
down_revision: Union[str, None] = "040_quality_signature"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE electronic_form_definitions "
        "SET name = '竹丝浸胶干燥生产记录表' "
        "WHERE form_key = 'DIPPING_DRYING' "
        "AND name = '配片数计量考核表'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE electronic_form_definitions "
        "SET name = '配片数计量考核表' "
        "WHERE form_key = 'DIPPING_DRYING' "
        "AND name = '竹丝浸胶干燥生产记录表'"
    )
