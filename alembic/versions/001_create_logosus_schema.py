"""Create logosus schema and tables.

Revision ID: 001_logosus
Revises:
Create Date: 2026-02-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_logosus'
down_revision: Union[str, None] = 'b4c8e3f56d92'  # Latest existing migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create logosus schema and all tables."""

    # Create schema (already created, but idempotent)
    op.execute("CREATE SCHEMA IF NOT EXISTS logosus")

    # =====================
    # Users table
    # =====================
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('picture', sa.Text, nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('provider', sa.String(50), default='email'),
        sa.Column('provider_id', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_verified', sa.Boolean, default=False),
        sa.Column('subscription_tier', sa.String(50), default='free'),
        sa.Column('subscription_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('settings', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        schema='logosus'
    )

    # =====================
    # API Keys table
    # =====================
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('key_prefix', sa.String(10), nullable=False),
        sa.Column('key_hash', sa.String(255), nullable=False),
        sa.Column('scopes', sa.Text, nullable=True),
        sa.Column('rate_limit', sa.Integer, default=1000),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        schema='logosus'
    )

    # =====================
    # Sessions table
    # =====================
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('refresh_token_hash', sa.String(255), nullable=False, unique=True),
        sa.Column('user_agent', sa.Text, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('device_info', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        schema='logosus'
    )

    # =====================
    # Projects table
    # =====================
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_public', sa.Boolean, default=False),
        sa.Column('settings', postgresql.JSONB, nullable=True),
        sa.Column('document_count', sa.Integer, default=0),
        sa.Column('conversation_count', sa.Integer, default=0),
        sa.Column('total_storage_bytes', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        schema='logosus'
    )

    # =====================
    # Conversations table
    # =====================
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.projects.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('summary', sa.Text, nullable=True),
        sa.Column('system_prompt', sa.Text, nullable=True),
        sa.Column('model', sa.String(100), default='gpt-4'),
        sa.Column('settings', postgresql.JSONB, nullable=True),
        sa.Column('message_count', sa.Integer, default=0),
        sa.Column('total_tokens', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        schema='logosus'
    )

    # =====================
    # Messages table
    # =====================
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.conversations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('tokens_input', sa.Integer, nullable=True),
        sa.Column('tokens_output', sa.Integer, nullable=True),
        sa.Column('agent_name', sa.String(100), nullable=True),
        sa.Column('agent_metadata', postgresql.JSONB, nullable=True),
        sa.Column('references', postgresql.JSONB, nullable=True),
        sa.Column('feedback_score', sa.Float, nullable=True),
        sa.Column('feedback_text', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        schema='logosus'
    )

    # =====================
    # Documents table
    # =====================
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('file_name', sa.String(500), nullable=False),
        sa.Column('file_type', sa.String(50), nullable=False),
        sa.Column('file_size', sa.Integer, nullable=False),
        sa.Column('file_path', sa.String(1000), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('doc_type', sa.String(50), default='general'),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('is_indexed', sa.Boolean, default=False, index=True),
        sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('index_error', sa.Text, nullable=True),
        sa.Column('chunk_count', sa.Integer, default=0),
        sa.Column('page_count', sa.Integer, nullable=True),
        sa.Column('word_count', sa.Integer, nullable=True),
        sa.Column('es_index', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_deleted', sa.Boolean, default=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        schema='logosus'
    )

    # =====================
    # Document Chunks table
    # =====================
    op.create_table(
        'document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('chunk_index', sa.Integer, nullable=False),
        sa.Column('page_number', sa.Integer, nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('start_char', sa.Integer, nullable=True),
        sa.Column('end_char', sa.Integer, nullable=True),
        sa.Column('es_chunk_id', sa.String(100), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema='logosus'
    )

    # =====================
    # Search History table
    # =====================
    op.create_table(
        'search_history',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.projects.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.conversations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('query', sa.Text, nullable=False),
        sa.Column('query_type', sa.String(50), default='default'),
        sa.Column('top_k', sa.Integer, default=5),
        sa.Column('min_score', sa.Float, default=0.0),
        sa.Column('include_images', sa.Boolean, default=False),
        sa.Column('result_count', sa.Integer, default=0),
        sa.Column('image_count', sa.Integer, default=0),
        sa.Column('top_score', sa.Float, nullable=True),
        sa.Column('avg_score', sa.Float, nullable=True),
        sa.Column('reranking_applied', sa.Boolean, default=False),
        sa.Column('source_documents', postgresql.JSONB, nullable=True),
        sa.Column('search_time_ms', sa.Integer, nullable=True),
        sa.Column('was_helpful', sa.Boolean, nullable=True),
        sa.Column('feedback', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
        schema='logosus'
    )

    # =====================
    # RAG Usage table
    # =====================
    op.create_table(
        'rag_usage',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('documents_uploaded', sa.Integer, default=0),
        sa.Column('documents_indexed', sa.Integer, default=0),
        sa.Column('total_chunks', sa.Integer, default=0),
        sa.Column('storage_bytes', sa.Integer, default=0),
        sa.Column('search_count', sa.Integer, default=0),
        sa.Column('image_search_count', sa.Integer, default=0),
        sa.Column('embedding_tokens', sa.Integer, default=0),
        sa.Column('avg_search_time_ms', sa.Float, nullable=True),
        sa.Column('avg_result_score', sa.Float, nullable=True),
        schema='logosus'
    )

    # =====================
    # Usage Stats table
    # =====================
    op.create_table(
        'usage_stats',
        sa.Column('id', postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), sa.ForeignKey('logosus.users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('date', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('api_calls', sa.Integer, default=0),
        sa.Column('api_errors', sa.Integer, default=0),
        sa.Column('chat_messages', sa.Integer, default=0),
        sa.Column('conversations_created', sa.Integer, default=0),
        sa.Column('tokens_input', sa.Integer, default=0),
        sa.Column('tokens_output', sa.Integer, default=0),
        sa.Column('agent_usage', postgresql.JSONB, nullable=True),
        sa.Column('model_usage', postgresql.JSONB, nullable=True),
        sa.Column('endpoint_usage', postgresql.JSONB, nullable=True),
        sa.Column('avg_response_time_ms', sa.Float, nullable=True),
        schema='logosus'
    )

    # Create indices
    op.create_index('ix_logosus_users_email', 'users', ['email'], schema='logosus')
    op.create_index('ix_logosus_documents_is_indexed', 'documents', ['is_indexed'], schema='logosus')
    op.create_index('ix_logosus_messages_created_at', 'messages', ['created_at'], schema='logosus')


def downgrade() -> None:
    """Drop all logosus tables."""
    op.drop_table('usage_stats', schema='logosus')
    op.drop_table('rag_usage', schema='logosus')
    op.drop_table('search_history', schema='logosus')
    op.drop_table('document_chunks', schema='logosus')
    op.drop_table('documents', schema='logosus')
    op.drop_table('messages', schema='logosus')
    op.drop_table('conversations', schema='logosus')
    op.drop_table('projects', schema='logosus')
    op.drop_table('sessions', schema='logosus')
    op.drop_table('api_keys', schema='logosus')
    op.drop_table('users', schema='logosus')
    op.execute("DROP SCHEMA IF EXISTS logosus CASCADE")
