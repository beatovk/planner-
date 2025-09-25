import os
import sys
import pytest

# Ensure project root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from apps.places.services.query_builder import create_query_builder
from apps.places.services.search import create_search_service
from apps.core.db import get_db
from apps.places.schemas.slots import SlotType


@pytest.fixture(scope="module")
def db_session():
    return next(get_db())


def test_build_slots_basic_triplet():
    builder = create_query_builder()
    q = "today i wanna chill, eat tom yum and go on the rooftop"
    result = builder.build_slots(q)
    assert len(result.slots) >= 3
    types = [s.type for s in result.slots]
    assert SlotType.VIBE in types
    assert SlotType.DISH in types
    assert SlotType.EXPERIENCE in types


def test_build_slots_fallback_when_missing():
    builder = create_query_builder()
    q = "totally unknown gibberish"
    result = builder.build_slots(q)
    # Should use fallback to reach up to 3 slots when enabled
    assert len(result.slots) >= 1
    assert result.fallback_used is True


def test_search_by_slot_vibe(db_session):
    builder = create_query_builder()
    search = create_search_service(db_session)
    res = builder.build_slots("chill")
    slot = next(s for s in res.slots if s.type == SlotType.VIBE)
    places = search.search_by_slot(slot, limit=5)
    assert isinstance(places, list)
    # Do not assert >0 because dataset can vary, but structure must be correct
    if places:
        assert "id" in places[0]
        assert "name" in places[0]


def test_search_by_slot_dish(db_session):
    builder = create_query_builder()
    search = create_search_service(db_session)
    res = builder.build_slots("tom yum")
    slot = next(s for s in res.slots if s.type in (SlotType.DISH, SlotType.CUISINE))
    places = search.search_by_slot(slot, limit=5)
    assert isinstance(places, list)
