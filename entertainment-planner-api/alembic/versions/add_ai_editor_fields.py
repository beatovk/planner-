"""add_ai_editor_fields

Revision ID: add_ai_editor_fields
Revises: e9eea0b88af9
Create Date: 2024-12-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_ai_editor_fields'
down_revision = '33b21fd4d800'
branch_labels = None
depends_on = None


def upgrade():
    # Add AI Editor Agent fields
    op.add_column('places', sa.Column('ai_verified', sa.Text(), nullable=True))
    op.add_column('places', sa.Column('ai_verification_date', sa.DateTime(), nullable=True))
    op.add_column('places', sa.Column('ai_verification_data', sa.Text(), nullable=True))


def downgrade():
    # Remove AI Editor Agent fields
    op.drop_column('places', 'ai_verification_data')
    op.drop_column('places', 'ai_verification_date')
    op.drop_column('places', 'ai_verified')
