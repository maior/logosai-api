"""Add agent registry tables (acp_servers, registered_agents).

Revision ID: 002_agent_registry
Revises: 001_logosus
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_agent_registry'
down_revision: Union[str, None] = '001_logosus'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create agent registry tables in logosus schema."""

    # =====================
    # ACP Servers table
    # =====================
    op.create_table(
        'acp_servers',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_default', sa.Boolean, default=False),
        sa.Column('health_status', sa.String(20), default='unknown'),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        schema='logosus'
    )

    # =====================
    # Registered Agents table
    # =====================
    op.create_table(
        'registered_agents',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('agent_id', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('acp_server_id', postgresql.UUID(as_uuid=False),
                  sa.ForeignKey('logosus.acp_servers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('capabilities', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('tags', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('input_type', sa.String(50), server_default='query'),
        sa.Column('output_type', sa.String(50), server_default='text'),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('display_name_ko', sa.String(255), nullable=True),
        sa.Column('icon', sa.String(10), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('priority', sa.Integer, default=50),
        sa.Column('is_available', sa.Boolean, default=True),
        sa.Column('average_execution_time_ms', sa.Float, nullable=True),
        sa.Column('success_rate', sa.Float, nullable=True),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(50), default='acp_sync'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        schema='logosus'
    )

    # Create additional indices (agent_id index already created by unique=True + index=True above)
    op.create_index('ix_logosus_registered_agents_is_available', 'registered_agents', ['is_available'], schema='logosus')
    op.create_index('ix_logosus_registered_agents_acp_server_id', 'registered_agents', ['acp_server_id'], schema='logosus')


def downgrade() -> None:
    """Drop agent registry tables."""
    op.drop_table('registered_agents', schema='logosus')
    op.drop_table('acp_servers', schema='logosus')
