"""create_core_platform_tables

Revision ID: 01a605e91e76
Revises: 
Create Date: 2026-10-01 07:57:33.118954

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '01a605e91e76'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = JSONB().with_variant(sa.JSON(), "sqlite").with_variant(sa.JSON(), "default")


def upgrade() -> None:
    # 1. Tenants
    op.create_table(
        'tenants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('slug', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('domain_type', sa.String(length=64), nullable=False),
        sa.Column('timezone', sa.String(length=64), server_default='Asia/Kolkata', nullable=False),
        sa.Column('primary_language', sa.String(length=16), server_default='mr', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True)

    # 2. Users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=64), server_default='OPERATOR', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'], unique=False)
    op.create_index('ix_users_email', 'users', ['email'], unique=False)
    op.create_index('ix_users_phone', 'users', ['phone'], unique=False)

    # 3. Tool Definitions
    op.create_table(
        'tool_definitions',
        sa.Column('id', sa.String(length=128), nullable=False),
        sa.Column('domain_key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('risk_level', sa.Integer(), server_default='1', nullable=False),
        sa.Column('requires_confirmation', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('parameters_schema', json_type, server_default='{}', nullable=False),
        sa.Column('is_global_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tool_definitions_domain_key', 'tool_definitions', ['domain_key'], unique=False)

    # 4. Tenant Enabled Tools
    op.create_table(
        'tenant_enabled_tools',
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('tool_id', sa.String(length=128), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('confirmation_policy', json_type, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tool_definitions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'tool_id'),
    )

    # 5. Voice Sessions
    op.create_table(
        'voice_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('channel', sa.String(length=64), server_default='web_voice', nullable=False),
        sa.Column('language_preference', sa.String(length=16), server_default='mr', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_voice_sessions_tenant_id', 'voice_sessions', ['tenant_id'], unique=False)
    op.create_index('ix_voice_sessions_user_id', 'voice_sessions', ['user_id'], unique=False)

    # 6. Action Executions
    op.create_table(
        'action_executions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=True),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('tool_id', sa.String(length=128), nullable=True),
        sa.Column('intent_detected', sa.String(length=128), nullable=False),
        sa.Column('extracted_parameters', json_type, server_default='{}', nullable=False),
        sa.Column('sanitized_parameters', json_type, server_default='{}', nullable=False),
        sa.Column('status', sa.String(length=32), server_default='PENDING_CONFIRMATION', nullable=False),
        sa.Column('risk_level', sa.Integer(), server_default='1', nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('execution_result', json_type, nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['voice_sessions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tool_id'], ['tool_definitions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_action_executions_session_id', 'action_executions', ['session_id'], unique=False)
    op.create_index('ix_action_executions_tenant_id', 'action_executions', ['tenant_id'], unique=False)
    op.create_index('ix_action_executions_user_id', 'action_executions', ['user_id'], unique=False)
    op.create_index('ix_action_executions_tool_id', 'action_executions', ['tool_id'], unique=False)
    op.create_index('ix_action_executions_status', 'action_executions', ['status'], unique=False)
    op.create_index('ix_action_executions_idempotency_key', 'action_executions', ['idempotency_key'], unique=False)
    op.create_index('ix_action_executions_created_at', 'action_executions', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('action_executions')
    op.drop_table('voice_sessions')
    op.drop_table('tenant_enabled_tools')
    op.drop_table('tool_definitions')
    op.drop_table('users')
    op.drop_table('tenants')
