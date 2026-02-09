"""Add user_memories table for personalized AI responses.

Revision ID: 003_user_memories
Revises: 002_agent_registry
Create Date: 2026-02-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_user_memories'
down_revision: Union[str, None] = '002_agent_registry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_memories table in logosus schema."""

    op.create_table(
        'user_memories',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False),
                   sa.ForeignKey('logosus.users.id', ondelete='CASCADE'),
                   nullable=False),
        sa.Column('memory_type', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('importance', sa.Float(), server_default='0.5'),
        sa.Column('source_conversation_id', postgresql.UUID(as_uuid=False),
                   sa.ForeignKey('logosus.conversations.id', ondelete='SET NULL'),
                   nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('access_count', sa.Integer(), server_default='0'),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema='logosus',
    )

    # Composite indexes for common queries
    op.create_index(
        'ix_user_memories_user_active',
        'user_memories',
        ['user_id', 'is_active'],
        schema='logosus',
    )
    op.create_index(
        'ix_user_memories_user_type',
        'user_memories',
        ['user_id', 'memory_type'],
        schema='logosus',
    )


def downgrade() -> None:
    """Drop user_memories table."""
    op.drop_index('ix_user_memories_user_type', table_name='user_memories', schema='logosus')
    op.drop_index('ix_user_memories_user_active', table_name='user_memories', schema='logosus')
    op.drop_table('user_memories', schema='logosus')
