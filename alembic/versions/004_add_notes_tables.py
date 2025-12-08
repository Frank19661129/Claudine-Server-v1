"""Add notes tables

Revision ID: 004
Revises: 003
Create Date: 2025-11-15 08:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create note_groups table
    op.create_table(
        'note_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=False, server_default='blue'),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_note_groups_user_id'), 'note_groups', ['user_id'], unique=False)

    # Create notes table
    op.create_table(
        'notes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=False, server_default='yellow'),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_checklist', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('categories', postgresql.ARRAY(sa.String()), nullable=True, server_default='{}'),
        sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_id'], ['note_groups.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notes_user_id'), 'notes', ['user_id'], unique=False)
    op.create_index('idx_notes_user_deleted', 'notes', ['user_id', 'deleted_at'], unique=False)
    op.create_index('idx_notes_search', 'notes', ['search_vector'], unique=False, postgresql_using='gin')

    # Create note_items table
    op.create_table(
        'note_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('note_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('is_checked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['note_id'], ['notes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_note_items_note_id'), 'note_items', ['note_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_note_items_note_id'), table_name='note_items')
    op.drop_table('note_items')
    op.drop_index('idx_notes_search', table_name='notes', postgresql_using='gin')
    op.drop_index('idx_notes_user_deleted', table_name='notes')
    op.drop_index(op.f('ix_notes_user_id'), table_name='notes')
    op.drop_table('notes')
    op.drop_index(op.f('ix_note_groups_user_id'), table_name='note_groups')
    op.drop_table('note_groups')
