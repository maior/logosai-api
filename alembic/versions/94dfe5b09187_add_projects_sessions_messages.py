"""Add projects sessions messages

Revision ID: 94dfe5b09187
Revises: 807622b10ed0
Create Date: 2026-01-29 15:56:04.197787

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '94dfe5b09187'
down_revision: Union[str, Sequence[str], None] = '807622b10ed0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create projects, sessions, and messages tables."""
    # Create projects table
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_projects_owner_id', 'projects', ['owner_id'])

    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_sessions_user_id', 'sessions', ['user_id'])
    op.create_index('ix_sessions_project_id', 'sessions', ['project_id'])

    # Create message_role enum
    message_role_enum = postgresql.ENUM('user', 'assistant', 'system', name='messagerole')
    message_role_enum.create(op.get_bind(), checkfirst=True)

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('role', message_role_enum, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('extra_data', postgresql.JSONB(), nullable=True),
        sa.Column('agent_type', sa.Text(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_messages_session_id', 'messages', ['session_id'])


def downgrade() -> None:
    """Drop messages, sessions, and projects tables."""
    op.drop_index('ix_messages_session_id', table_name='messages')
    op.drop_table('messages')

    # Drop message_role enum
    message_role_enum = postgresql.ENUM('user', 'assistant', 'system', name='messagerole')
    message_role_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index('ix_sessions_project_id', table_name='sessions')
    op.drop_index('ix_sessions_user_id', table_name='sessions')
    op.drop_table('sessions')

    op.drop_index('ix_projects_owner_id', table_name='projects')
    op.drop_table('projects')
