import os
import sys
import asyncio
import pytest

# Ensure project root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from apps.api.routes.compose import _compose_slotter_rails
from apps.core.db import get_db


@pytest.mark.parametrize("q", [
    "i wanna chill tom yum and rooftop",
    "i wanna chill matcha and rooftop",
    "today i wanna chill, eat tom yum and go on the rooftop",
])
def test_compose_slotter_three_rails_sync_param(q):
    db = next(get_db())

    async def _run():
        return await _compose_slotter_rails(
            q=q,
            area=None,
            user_lat=13.7563,
            user_lng=100.5018,
            quality_only=False,
            db=db
        )

    result = asyncio.run(_run())
    assert result.rails is not None
    # Должно быть ровно 3 рельсы (включая fallback при необходимости)
    assert len(result.rails) == 3
    # Базовая проверка наполнения: хотя бы по 6 карточек в первой рельсе (MVP критерий)
    # Не делаем слишком строгую проверку на все 3, чтобы не флапало на бедных районах
    assert len(result.rails[0].items) >= 6
    # Структура карточек корректна
    first = result.rails[0].items[0] if result.rails[0].items else None
    assert first is not None and hasattr(first, 'id') and hasattr(first, 'name')
