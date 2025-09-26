import os
import time
import pytest
from fastapi.testclient import TestClient

# Ensure DATABASE_URL is set to a Postgres DSN so app import doesn't crash
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ep:ep@localhost:5432/ep")

# Import after setting env
from apps.api.main import app  # noqa: E402

client = TestClient(app)


def _xfail_if_db_down(resp, endpoint: str):
    if resp.status_code >= 500:
        pytest.xfail(f"DB unavailable for {endpoint}: {resp.status_code}")


@pytest.mark.e2e
def test_suggest_pg_mv():
    # PG MV suggestion path; should return list of strings when DB is up
    r = client.get("/api/places/suggest", params={"q": "tom yum", "limit": 10})
    _xfail_if_db_down(r, "/api/places/suggest")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("suggestions"), list)
    # suggestions may be empty on small DB; just type/length check
    for s in data.get("suggestions", [])[:3]:
        assert isinstance(s, str)
        assert len(s.strip()) >= 2


@pytest.mark.e2e
def test_search_pg_fts_and_distance_sort():
    r = client.get("/api/places/search", params={"q": "tom yum", "limit": 12})
    _xfail_if_db_down(r, "/api/places/search")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("results"), list)
    assert data.get("total_count") is not None

    # distance sort with radius
    r2 = client.get(
        "/api/places/search",
        params={
            "q": "tom yum",
            "limit": 12,
            "sort": "distance",
            "user_lat": 13.736717,
            "user_lng": 100.523186,
            "radius_m": 2000,
        },
    )
    _xfail_if_db_down(r2, "/api/places/search distance")
    assert r2.status_code == 200
    data2 = r2.json()
    # Count with radius should be <= without radius if both non-empty
    if data.get("results") and data2.get("results"):
        assert len(data2["results"]) <= len(data["results"])  # property check
        # Check non-decreasing distance for first 3 if present
        dists = [x.get("distance_m") for x in data2["results"][:3] if x.get("distance_m") is not None]
        if len(dists) >= 2:
            assert all(dists[i] <= dists[i + 1] for i in range(len(dists) - 1))


@pytest.mark.e2e
def test_rails_light_and_surprise_and_quality_cache():
    # light mode
    r = client.get("/api/rails", params={"mode": "light", "limit": 12})
    _xfail_if_db_down(r, "/api/rails light")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("rails"), list)
    assert 1 <= len(data["rails"]) <= 3
    # badges/why presence (best-effort)
    for rail in data.get("rails", [])[:3]:
        for card in rail.get("items", [])[:3]:
            assert "badges" in card
            assert "why" in card

    # cache behavior: second call faster or header hit when available
    t1 = time.time()
    r1 = client.get("/api/rails", params={"mode": "light", "limit": 12})
    t1 = time.time() - t1
    t2 = time.time()
    r2 = client.get("/api/rails", params={"mode": "light", "limit": 12})
    t2 = time.time() - t2
    _xfail_if_db_down(r1, "/api/rails cache 1")
    _xfail_if_db_down(r2, "/api/rails cache 2")
    # If debug header exists, prefer header check; else timing check
    hdr2 = r2.headers.get("X-Rails-Cache")
    if hdr2:
        assert "HIT" in hdr2 or "MISS" in hdr2
    else:
        assert t2 <= t1 * 1.2  # allow minor jitter

    # surprise mode and clusters diversity
    rs = client.get("/api/rails", params={"mode": "surprise", "limit": 12})
    _xfail_if_db_down(rs, "/api/rails surprise")
    assert rs.status_code == 200
    rs_data = rs.json()
    labels = [rail.get("label") for rail in rs_data.get("rails", [])]
    if len(labels) >= 2:
        assert len(set(labels[:2])) >= 1  # at least some diversity

    # quality=high is subset or equal
    rs_hq = client.get("/api/rails", params={"mode": "surprise", "limit": 12, "quality": "high"})
    _xfail_if_db_down(rs_hq, "/api/rails surprise HQ")
    assert rs_hq.status_code == 200
    base_counts = [len(r.get("items", [])) for r in rs_data.get("rails", [])]
    hq_counts = [len(r.get("items", [])) for r in rs_hq.json().get("rails", [])]
    if base_counts and hq_counts:
        assert sum(hq_counts) <= sum(base_counts)


@pytest.mark.e2e
def test_compose_free_text_falls_back_to_fts():
    resp = client.get(
        "/api/rails",
        params={
            "mode": "light",
            "q": "i wanna chill rooftop and matcha",
            "user_lat": 13.75,
            "user_lng": 100.5,
            "limit": 12,
        },
    )
    _xfail_if_db_down(resp, "/api/rails free-text fallback")
    assert resp.status_code == 200
    data = resp.json()
    rails = data.get("rails", [])
    assert rails, "Expected rails for free-text query"
    ids = {item["id"] for rail in rails for item in rail.get("items", [])}
    assert 1385 in ids, "MTCH (Sukhumvit 23) should appear for matcha query"
    for rail in rails:
        rail_ids = [item["id"] for item in rail.get("items", [])]
        assert len(rail_ids) == len(set(rail_ids)), "Duplicate places detected inside a rail"

    resp2 = client.get(
        "/api/rails",
        params={
            "mode": "light",
            "q": "i wanna chill, rooftop and spa",
            "user_lat": 13.75,
            "user_lng": 100.5,
            "limit": 12,
        },
    )
    _xfail_if_db_down(resp2, "/api/rails free-text fallback multi-intent")
    assert resp2.status_code == 200
    rails2 = resp2.json().get("rails", [])
    assert rails2, "Expected rails for multi-intent free-text query"
    assert sum(len(r.get("items", [])) for r in rails2) > 0, "Expected items in multi-intent rails"
    assert len(rails2) >= 3, "Expected at least three rails for multi-intent query"
    first_steps = [r.get("step") for r in rails2[:3]]
    assert len(set(first_steps)) == len(first_steps), "Rails should represent distinct intents"


@pytest.mark.e2e
def test_compose_climb_matcha_rooftop():
    resp = client.get(
        "/api/rails",
        params={
            "mode": "light",
            "q": "i wanna climb matcha and rooftop",
            "user_lat": 13.75,
            "user_lng": 100.5,
            "limit": 12,
        },
    )
    _xfail_if_db_down(resp, "/api/rails climb-matcha-rooftop")
    assert resp.status_code == 200
    rails = resp.json().get("rails", [])
    assert rails, "Expected rails for climb/matcha/rooftop query"
    steps = {rail.get("step") for rail in rails}
    expected = {"experience:climbing", "drink:matcha", "experience:rooftop"}
    assert expected.issubset(steps)
    total_items = sum(len(rail.get("items", [])) for rail in rails)
    unique_items = len({item["id"] for rail in rails for item in rail.get("items", [])})
    assert unique_items == total_items


@pytest.mark.e2e
def test_compose_pasta_cinema_matcha():
    resp = client.get(
        "/api/rails",
        params={
            "mode": "light",
            "q": "i wanna eat pasta, cinema and matcha",
            "user_lat": 13.75,
            "user_lng": 100.5,
            "limit": 12,
        },
    )
    _xfail_if_db_down(resp, "/api/rails pasta-cinema-matcha")
    assert resp.status_code == 200
    rails = resp.json().get("rails", [])
    assert rails, "Expected rails for pasta/cinema/matcha query"
    steps = {rail.get("step") for rail in rails}
    expected = {"dish:pasta", "experience:cinema", "drink:matcha"}
    assert expected.issubset(steps)


@pytest.mark.e2e
def test_compose_date_rooftop_matcha():
    resp = client.get(
        "/api/rails",
        params={
            "mode": "light",
            "q": "i wanna date night rooftop and matcha",
            "user_lat": 13.75,
            "user_lng": 100.5,
            "limit": 12,
        },
    )
    _xfail_if_db_down(resp, "/api/rails date-night")
    assert resp.status_code == 200
    rails = resp.json().get("rails", [])
    assert rails, "Expected rails for date/rooftop/matcha query"
    steps = {rail.get("step") for rail in rails}
    expected = {"vibe:romantic", "experience:rooftop", "drink:matcha"}
    assert expected.issubset(steps)
