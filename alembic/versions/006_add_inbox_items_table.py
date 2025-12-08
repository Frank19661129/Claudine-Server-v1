"""Add inbox items table

Revision ID: 006
Revises: 004
Create Date: 2025-11-15 21:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create inbox_items table
    op.create_table(
        'inbox_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),  # email, event, message, notification, web_clip, file
        sa.Column('source', sa.String(100), nullable=False),  # gmail, outlook, manual, etc.
        sa.Column('status', sa.String(50), nullable=False, server_default='unprocessed'),  # unprocessed, pending_review, accepted, modified, rejected, archived
        sa.Column('priority', sa.String(20), nullable=False, server_default='medium'),  # low, medium, high, urgent
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('raw_data', postgresql.JSONB, nullable=True),
        sa.Column('ai_suggestion', postgresql.JSONB, nullable=True),
        sa.Column('user_decision', postgresql.JSONB, nullable=True),
        sa.Column('linked_items', postgresql.JSONB, nullable=True, server_default='[]'),
        sa.Column('processed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Create indexes
    op.create_index('idx_inbox_items_user_status', 'inbox_items', ['user_id', 'status'])
    op.create_index('idx_inbox_items_type', 'inbox_items', ['type'])
    op.create_index('idx_inbox_items_created', 'inbox_items', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_inbox_items_created')
    op.drop_index('idx_inbox_items_type')
    op.drop_index('idx_inbox_items_user_status')
    op.drop_table('inbox_items')
