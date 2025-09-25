"""add_shadow_schema_fields

Revision ID: c31814682c27
Revises: add_ai_editor_fields
Create Date: 2025-09-12 15:09:25.017285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c31814682c27'
down_revision: Union[str, Sequence[str], None] = 'add_ai_editor_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем поля для теневой схемы протокола
    op.add_column('places', sa.Column('attempts', sa.Text, nullable=True, default='{}'))
    op.add_column('places', sa.Column('quality_flags', sa.Text, nullable=True, default='{}'))
    
    # Создаем таблицу для событий места
    op.create_table('place_events',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('place_id', sa.Integer, nullable=False),
        sa.Column('agent', sa.String(50), nullable=False),
        sa.Column('code', sa.String(100), nullable=True),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('note', sa.Text, nullable=True),
        sa.Column('ts', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.ForeignKeyConstraint(['place_id'], ['places.id'], ondelete='CASCADE')
    )
    
    # Создаем индексы для производительности
    op.create_index('ix_place_events_place_id', 'place_events', ['place_id'])
    op.create_index('ix_place_events_agent', 'place_events', ['agent'])
    op.create_index('ix_place_events_ts', 'place_events', ['ts'])


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем таблицу событий
    op.drop_table('place_events')
    
    # Удаляем добавленные поля
    op.drop_column('places', 'quality_flags')
    op.drop_column('places', 'attempts')
