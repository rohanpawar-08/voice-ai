"""add_idempotency_unique_index

Revision ID: b92ed35af719
Revises: 01a605e91e76
Create Date: 2026-10-10 10:00:24.692002

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b92ed35af719'
down_revision: Union[str, Sequence[str], None] = '01a605e91e76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add unique partial index on (tenant_id, idempotency_key)."""
    op.create_index(
        'uq_action_executions_tenant_idempotency',
        'action_executions',
        ['tenant_id', 'idempotency_key'],
        unique=True,
        postgresql_where=sa.text('idempotency_key IS NOT NULL')
    )


def downgrade() -> None:
    """Downgrade schema: Drop unique partial index."""
    op.drop_index(
        'uq_action_executions_tenant_idempotency',
        table_name='action_executions'
    )
