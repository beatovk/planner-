"""Add interest_signals field to Place model

Revision ID: add_interest_signals_field
Revises: f8912301f0c0
Create Date: 2025-01-16 11:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_interest_signals_field'
down_revision = '64c7b2d304ed'
branch_labels = None
depends_on = None


def upgrade():
    # Add interest_signals field to places table
    op.add_column('places', sa.Column('interest_signals', sa.JSON(), nullable=True))


def downgrade():
    # Remove interest_signals field from places table
    op.drop_column('places', 'interest_signals')
