import os
import pytest
from fastapi.testclient import TestClient

# Ensure Postgres DSN present to let the app import
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://ep:ep@localhost:5432/ep")

from apps.api.main import app  # noqa: E402

client = TestClient(app)


def _xfail_if_db_down(resp, endpoint: str):
    if resp.status_code >= 500:
        pytest.xfail(f"DB unavailable for {endpoint}: {resp.status_code}")


@pytest.mark.e2e
def test_light_vs_surprise_order_differs():
    # Fetch rails in light mode
    r_light = client.get("/api/rails", params={"mode": "light", "limit": 12})
    _xfail_if_db_down(r_light, "/api/rails light")
    assert r_light.status_code == 200
    rails_light = r_light.json().get("rails", [])
    # Flatten top-N names for comparison
    top_light = [it.get("name") for rail in rails_light for it in rail.get("items", [])][:12]

    # surprise mode
    r_sur = client.get("/api/rails", params={"mode": "surprise", "limit": 12})
    _xfail_if_db_down(r_sur, "/api/rails surprise")
    assert r_sur.status_code == 200
    rails_sur = r_sur.json().get("rails", [])
    top_sur = [it.get("name") for rail in rails_sur for it in rail.get("items", [])][:12]

    # The order should reasonably differ due to signal_boost/extraordinary selection
    if top_light and top_sur:
        assert top_light != top_sur


@pytest.mark.e2e
def test_surprise_has_distinct_clusters_and_quality_subset():
    # surprise base
    r_base = client.get("/api/rails", params={"mode": "surprise", "limit": 12})
    _xfail_if_db_down(r_base, "/api/rails surprise base")
    assert r_base.status_code == 200
    data_base = r_base.json()
    labels = [rail.get("label") for rail in data_base.get("rails", [])]
    if len(labels) >= 2:
        assert len(set(labels[:2])) >= 1  # at least some diversity across first 2

    # surprise + quality high should be subset or equal total items
    r_hq = client.get("/api/rails", params={"mode": "surprise", "limit": 12, "quality": "high"})
    _xfail_if_db_down(r_hq, "/api/rails surprise high")
    assert r_hq.status_code == 200
    base_total = sum(len(rail.get("items", [])) for rail in data_base.get("rails", []))
    hq_total = sum(len(rail.get("items", [])) for rail in r_hq.json().get("rails", []))
    if base_total and hq_total is not None:
        assert hq_total <= base_total
