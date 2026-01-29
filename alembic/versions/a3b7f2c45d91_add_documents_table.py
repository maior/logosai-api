"""Add documents table

Revision ID: a3b7f2c45d91
Revises: 94dfe5b09187
Create Date: 2026-01-29 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a3b7f2c45d91'
down_revision: Union[str, Sequence[str], None] = '94dfe5b09187'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create documents table."""
    # Create document_status enum
    document_status_enum = postgresql.ENUM(
        'pending', 'processing', 'completed', 'failed',
        name='documentstatus'
    )
    document_status_enum.create(op.get_bind(), checkfirst=True)

    # Create document_type enum
    document_type_enum = postgresql.ENUM(
        'pdf', 'txt', 'markdown', 'docx', 'csv', 'json', 'other',
        name='documenttype'
    )
    document_type_enum.create(op.get_bind(), checkfirst=True)

    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        # Owner
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=False), nullable=True),
        # File info
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('original_filename', sa.String(500), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('document_type', document_type_enum, nullable=False, server_default='other'),
        # Processing status
        sa.Column('status', document_status_enum, nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        # Content metadata
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('language', sa.String(10), nullable=True),
        # Vector store info (for RAG)
        sa.Column('vector_store_id', sa.String(255), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        # Extra metadata
        sa.Column('extra_metadata', postgresql.JSONB(), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    )

    # Create indexes
    op.create_index('ix_documents_user_id', 'documents', ['user_id'])
    op.create_index('ix_documents_project_id', 'documents', ['project_id'])
    op.create_index('ix_documents_status', 'documents', ['status'])


def downgrade() -> None:
    """Drop documents table."""
    op.drop_index('ix_documents_status', table_name='documents')
    op.drop_index('ix_documents_project_id', table_name='documents')
    op.drop_index('ix_documents_user_id', table_name='documents')
    op.drop_table('documents')

    # Drop enums
    document_type_enum = postgresql.ENUM(
        'pdf', 'txt', 'markdown', 'docx', 'csv', 'json', 'other',
        name='documenttype'
    )
    document_type_enum.drop(op.get_bind(), checkfirst=True)

    document_status_enum = postgresql.ENUM(
        'pending', 'processing', 'completed', 'failed',
        name='documentstatus'
    )
    document_status_enum.drop(op.get_bind(), checkfirst=True)
