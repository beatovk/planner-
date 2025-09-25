"""add_google_maps_fields

Revision ID: 2b90f17b5877
Revises: 1e5d3814ad72
Create Date: 2025-09-06 10:43:34.416322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b90f17b5877'
down_revision: Union[str, Sequence[str], None] = '1e5d3814ad72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add Google Maps fields
    op.add_column('places', sa.Column('business_status', sa.Text(), nullable=True))
    op.add_column('places', sa.Column('utc_offset_minutes', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove Google Maps fields
    op.drop_column('places', 'utc_offset_minutes')
    op.drop_column('places', 'business_status')
