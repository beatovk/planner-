"""merge_heads

Revision ID: 3087b75a3bf8
Revises: 005_create_epx_schema_and_mv, 005_extend_places_search_for_slotter
Create Date: 2025-09-27 14:42:24.407251

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3087b75a3bf8'
down_revision: Union[str, Sequence[str], None] = ('005_create_epx_schema_and_mv', '005_extend_places_search_for_slotter')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
