"""Add photo_url to users table

Revision ID: 007
Revises: 006
Create Date: 2025-11-16 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add photo_url column to users table
    op.add_column('users', sa.Column('photo_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    # Remove photo_url column from users table
    op.drop_column('users', 'photo_url')
