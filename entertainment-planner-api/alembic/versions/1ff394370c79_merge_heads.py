"""merge_heads

Revision ID: 1ff394370c79
Revises: 004_create_epx_schema, de0311f798f2
Create Date: 2025-09-26 20:02:20.396495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ff394370c79'
down_revision: Union[str, Sequence[str], None] = ('004_create_epx_schema', 'de0311f798f2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
