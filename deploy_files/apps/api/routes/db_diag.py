from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.engine import Engine
from apps.core.db import engine

router = APIRouter()

def _dialect(e: Engine) -> str:
    try:
        return (e.dialect.name or "unknown").lower()
    except Exception:
        return "unknown"

@router.get("/health/db_diag")
def db_diag():
    out = {"driver": _dialect(engine), "connected": False}

    try:
        if out["driver"] == "postgresql":
            with engine.begin() as c:
                out["connected"] = True
                out["has_epx"] = bool(c.execute(text(
                    "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname='epx')"
                )).scalar())
                out["has_mv"] = bool(c.execute(text(
                    "SELECT to_regclass('epx.places_search_mv') IS NOT NULL"
                )).scalar())

                if out["has_mv"]:
                    out["mv_count"] = int(c.execute(text(
                        "SELECT count(*) FROM epx.places_search_mv"
                    )).scalar())

                    # агрегаты по MV безопасно только при has_mv
                    out["by_cat"] = [
                        {"cat": r[0], "count": int(r[1])}
                        for r in c.execute(text(
                            "SELECT lower(category) AS cat, count(*) "
                            "FROM epx.places_search_mv GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                        ))
                    ]

                    out["romantic_cnt"] = int(c.execute(text(
                        "SELECT count(*) FROM epx.places_search_mv WHERE is_romantic = true"
                    )).scalar())

                    out["chill_cnt"] = int(c.execute(text(
                        "SELECT count(*) FROM epx.places_search_mv WHERE is_chill = true"
                    )).scalar())

                    out["cinema_cnt"] = int(c.execute(text(
                        "SELECT count(*) FROM epx.places_search_mv WHERE is_cinema = true"
                    )).scalar())

        elif out["driver"] in ("sqlite", "sqlite+pysqlite"):
            with engine.begin() as c:
                out["connected"] = True

                # Есть ли таблица places?
                has_places = bool(c.execute(text(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='places'"
                )).first())
                out["has_places"] = has_places

                if has_places:
                    out["places_count"] = int(c.execute(text(
                        "SELECT COUNT(*) FROM places"
                    )).scalar())

                    # by_cat может не быть — пробуем мягко
                    try:
                        out["by_cat"] = [
                            {"cat": r[0], "count": int(r[1])}
                            for r in c.execute(text(
                                "SELECT lower(category) AS cat, count(*) "
                                "FROM places GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                            ))
                        ]
                    except Exception as e:
                        out["by_cat_error"] = repr(e)

                    # Простейшие счётчики (если нет signals) — эвристики по category
                    try:
                        out["romantic_cnt"] = int(c.execute(text(
                            "SELECT count(*) FROM places "
                            "WHERE lower(coalesce(category,'')) LIKE '%romantic%' "
                            "   OR lower(coalesce(category,'')) LIKE '%date%'"
                        )).scalar())
                    except Exception as e:
                        out["romantic_cnt"] = {"error": repr(e)}

                    try:
                        out["chill_cnt"] = int(c.execute(text(
                            "SELECT count(*) FROM places "
                            "WHERE lower(coalesce(category,'')) LIKE '%spa%' "
                            "   OR lower(coalesce(category,'')) LIKE '%lounge%' "
                            "   OR lower(coalesce(category,'')) LIKE '%park%'"
                        )).scalar())
                    except Exception as e:
                        out["chill_cnt"] = {"error": repr(e)}

                    try:
                        out["cinema_cnt"] = int(c.execute(text(
                            "SELECT count(*) FROM places "
                            "WHERE lower(coalesce(category,'')) LIKE '%cinema%' "
                            "   OR lower(coalesce(category,'')) LIKE '%movie%'"
                        )).scalar())
                    except Exception as e:
                        out["cinema_cnt"] = {"error": repr(e)}
                else:
                    out["places_count"] = 0
        else:
            out["error"] = f"unsupported driver: {out['driver']}"

    except Exception as e:
        out["error"] = str(e)

    return out