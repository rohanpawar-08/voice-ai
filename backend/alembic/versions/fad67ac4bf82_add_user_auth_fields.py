"""add_user_auth_fields

Revision ID: fad67ac4bf82
Revises: b92ed35af719
Create Date: 2026-10-10 12:38:53.790505

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fad67ac4bf82'
down_revision: Union[str, Sequence[str], None] = 'b92ed35af719'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add hashed_password, last_login_at to users table."""
    op.add_column('users', sa.Column('hashed_password', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_users_tenant_email', 'users', ['tenant_id', 'email'], unique=False)


def downgrade() -> None:
    """Downgrade schema: Remove auth columns and index from users table."""
    op.drop_index('ix_users_tenant_email', table_name='users')
    op.drop_column('users', 'last_login_at')
    op.drop_column('users', 'hashed_password')
