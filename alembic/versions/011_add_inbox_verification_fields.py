"""Add inbox verification fields

Revision ID: 011
Revises: 010
Create Date: 2024-12-10
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add inbox verification fields
    op.add_column('users', sa.Column('inbox_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('inbox_verification_token', sa.String(64), nullable=True))
    op.add_column('users', sa.Column('inbox_verification_expires', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'inbox_verification_expires')
    op.drop_column('users', 'inbox_verification_token')
    op.drop_column('users', 'inbox_verified')
