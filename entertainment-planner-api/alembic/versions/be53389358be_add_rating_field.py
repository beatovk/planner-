"""add_rating_field

Revision ID: be53389358be
Revises: bf5e622b9374
Create Date: 2025-09-17 11:44:47.522975

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be53389358be'
down_revision: Union[str, Sequence[str], None] = 'bf5e622b9374'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('places', sa.Column('rating', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('places', 'rating')
