"""Change photo_url column type to TEXT

Revision ID: 008
Revises: 007
Create Date: 2025-11-16 13:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Change photo_url column type from VARCHAR(500) to TEXT to support base64 data URLs
    op.alter_column('users', 'photo_url',
                   existing_type=sa.String(length=500),
                   type_=sa.Text(),
                   existing_nullable=True)


def downgrade() -> None:
    # Change photo_url column type back to VARCHAR(500)
    op.alter_column('users', 'photo_url',
                   existing_type=sa.Text(),
                   type_=sa.String(length=500),
                   existing_nullable=True)
