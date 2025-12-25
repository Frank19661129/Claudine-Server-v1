"""Add user onboarding fields

Revision ID: 010
Revises: 009
Create Date: 2025-12-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email verification fields
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('email_verification_code', sa.String(6), nullable=True))
    op.add_column('users', sa.Column('email_verification_expires', sa.DateTime(), nullable=True))

    # Add phone fields
    op.add_column('users', sa.Column('phone_number', sa.String(20), nullable=True))
    op.add_column('users', sa.Column('phone_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('phone_verification_code', sa.String(6), nullable=True))
    op.add_column('users', sa.Column('phone_verification_expires', sa.DateTime(), nullable=True))

    # Add inbox address fields
    op.add_column('users', sa.Column('inbox_prefix', sa.String(64), nullable=True))
    op.add_column('users', sa.Column('inbox_token', sa.String(6), nullable=True))

    # Add onboarding status
    op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))

    # Create unique index on inbox address combo
    op.create_index('ix_users_inbox_address', 'users', ['inbox_prefix', 'inbox_token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_inbox_address', table_name='users')
    op.drop_column('users', 'onboarding_completed')
    op.drop_column('users', 'inbox_token')
    op.drop_column('users', 'inbox_prefix')
    op.drop_column('users', 'phone_verification_expires')
    op.drop_column('users', 'phone_verification_code')
    op.drop_column('users', 'phone_verified')
    op.drop_column('users', 'phone_number')
    op.drop_column('users', 'email_verification_expires')
    op.drop_column('users', 'email_verification_code')
    op.drop_column('users', 'email_verified')
