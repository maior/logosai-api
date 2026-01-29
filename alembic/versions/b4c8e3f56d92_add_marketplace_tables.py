"""Add marketplace tables

Revision ID: b4c8e3f56d92
Revises: a3b7f2c45d91
Create Date: 2026-01-29 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b4c8e3f56d92'
down_revision: Union[str, Sequence[str], None] = 'a3b7f2c45d91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create marketplace tables."""
    # Create agent_status enum
    agent_status_enum = postgresql.ENUM(
        'draft', 'pending', 'published', 'rejected', 'suspended', 'archived',
        name='agentstatus'
    )
    agent_status_enum.create(op.get_bind(), checkfirst=True)

    # Create pricing_type enum
    pricing_type_enum = postgresql.ENUM(
        'free', 'one_time', 'subscription', 'usage_based',
        name='pricingtype'
    )
    pricing_type_enum.create(op.get_bind(), checkfirst=True)

    # Create marketplace_agents table
    op.create_table(
        'marketplace_agents',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        # Basic info
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('short_description', sa.String(500), nullable=True),
        # Creator
        sa.Column('creator_id', postgresql.UUID(as_uuid=False), nullable=False),
        # Status
        sa.Column('status', agent_status_enum, nullable=False, server_default='draft'),
        # Categorization
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.String(50)), nullable=True),
        # Pricing
        sa.Column('pricing_type', pricing_type_enum, nullable=False, server_default='free'),
        sa.Column('price', sa.Numeric(10, 2), nullable=True, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        # Media
        sa.Column('icon_url', sa.String(500), nullable=True),
        sa.Column('banner_url', sa.String(500), nullable=True),
        sa.Column('screenshots', postgresql.ARRAY(sa.String(500)), nullable=True),
        # Agent configuration
        sa.Column('agent_type', sa.String(100), nullable=False),
        sa.Column('agent_config', postgresql.JSONB(), nullable=True),
        sa.Column('capabilities', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('requirements', postgresql.JSONB(), nullable=True),
        # Version info
        sa.Column('version', sa.String(50), nullable=False, server_default='1.0.0'),
        sa.Column('changelog', sa.Text(), nullable=True),
        # Stats
        sa.Column('download_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rating_average', sa.Numeric(3, 2), nullable=True),
        sa.Column('rating_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('review_count', sa.Integer(), nullable=False, server_default='0'),
        # Visibility
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_marketplace_agents_creator_id', 'marketplace_agents', ['creator_id'])
    op.create_index('ix_marketplace_agents_category', 'marketplace_agents', ['category'])
    op.create_index('ix_marketplace_agents_slug', 'marketplace_agents', ['slug'])
    op.create_index('ix_marketplace_agents_status', 'marketplace_agents', ['status'])

    # Create agent_reviews table
    op.create_table(
        'agent_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        # References
        sa.Column('agent_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        # Review content
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        # Moderation
        sa.Column('is_verified_purchase', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default='false'),
        # Helpfulness
        sa.Column('helpful_count', sa.Integer(), nullable=False, server_default='0'),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id', 'user_id', name='uq_agent_user_review'),
        sa.ForeignKeyConstraint(['agent_id'], ['marketplace_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_agent_reviews_agent_id', 'agent_reviews', ['agent_id'])
    op.create_index('ix_agent_reviews_user_id', 'agent_reviews', ['user_id'])

    # Create agent_purchases table
    op.create_table(
        'agent_purchases',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        # References
        sa.Column('agent_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=False), nullable=False),
        # Purchase info
        sa.Column('pricing_type', pricing_type_enum, nullable=False),
        sa.Column('amount_paid', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        # Subscription specific
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        # Transaction
        sa.Column('transaction_id', sa.String(255), nullable=True),
        sa.Column('payment_method', sa.String(50), nullable=True),
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agent_id'], ['marketplace_agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_agent_purchases_agent_id', 'agent_purchases', ['agent_id'])
    op.create_index('ix_agent_purchases_user_id', 'agent_purchases', ['user_id'])


def downgrade() -> None:
    """Drop marketplace tables."""
    # Drop agent_purchases
    op.drop_index('ix_agent_purchases_user_id', table_name='agent_purchases')
    op.drop_index('ix_agent_purchases_agent_id', table_name='agent_purchases')
    op.drop_table('agent_purchases')

    # Drop agent_reviews
    op.drop_index('ix_agent_reviews_user_id', table_name='agent_reviews')
    op.drop_index('ix_agent_reviews_agent_id', table_name='agent_reviews')
    op.drop_table('agent_reviews')

    # Drop marketplace_agents
    op.drop_index('ix_marketplace_agents_status', table_name='marketplace_agents')
    op.drop_index('ix_marketplace_agents_slug', table_name='marketplace_agents')
    op.drop_index('ix_marketplace_agents_category', table_name='marketplace_agents')
    op.drop_index('ix_marketplace_agents_creator_id', table_name='marketplace_agents')
    op.drop_table('marketplace_agents')

    # Drop enums
    pricing_type_enum = postgresql.ENUM(
        'free', 'one_time', 'subscription', 'usage_based',
        name='pricingtype'
    )
    pricing_type_enum.drop(op.get_bind(), checkfirst=True)

    agent_status_enum = postgresql.ENUM(
        'draft', 'pending', 'published', 'rejected', 'suspended', 'archived',
        name='agentstatus'
    )
    agent_status_enum.drop(op.get_bind(), checkfirst=True)
