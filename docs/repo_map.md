# Repository Map & Phase 0 Triage

This document captures the high-level architecture and current reliability risks for the Entertainment Planner repo. It establishes the baseline required before starting cleanup and hardening work.

## Services & Entry Points

| Service | Entry point | Host/Port | Notes |
|---------|-------------|-----------|-------|
| FastAPI backend | `uvicorn apps.api.main:app` | `0.0.0.0:$PORT` (default 8000) | Mounts REST API under `/api`, serves static mobile UI at `/` and `/web2`. Background task refreshes `epx.places_search_mv()` every 5 minutes. |
| Static web (web2) | `apps/web-mobile/web2/index.html` | Built as static assets | Vanilla JS fetches `/api/compose/rails` (aka `/api/rails`) and renders Netflix-style rails. |

* `apps/api/main.py` wires routers, configures CORS (`*`), and exposes `/health/db` plus a JSON root banner. A DB-refresh loop is registered on startup.【F:entertainment-planner-api/apps/api/main.py†L1-L69】
* Health router currently hits PostgreSQL on every `/health` request, so it is **not** constant-time and depends on DB availability.【F:entertainment-planner-api/apps/api/routes/health.py†L16-L55】
* Static mounting makes the backend the single deployment target; no separate Node/SSR runtime is present.【F:entertainment-planner-api/apps/api/main.py†L30-L36】

## Dependency Snapshot

### Python

* Runtime: Python 3.11 via Dockerfile base image and pinned `requirements.txt` (FastAPI 0.116, SQLAlchemy 2.0, Pydantic 2.11, Uvicorn 0.35, OpenAI 1.51).【F:Dockerfile†L1-L24】【F:entertainment-planner-api/requirements.txt†L1-L32】
* Settings managed through `pydantic-settings`; `.env` expected in project root. PostgreSQL-only connections enforced in `apps.core.db` with pooling defaults (pool size 5, max overflow 10).【F:entertainment-planner-api/apps/core/config.py†L1-L34】【F:entertainment-planner-api/apps/core/db.py†L1-L60】

### Frontend

* Pure HTML/CSS/JS assets in `apps/web-mobile/web2`. No package.json or bundler; default state makes `/web2/app1.js` the main bundle handling fetch/render logic and Google Maps integration.【F:entertainment-planner-api/apps/web-mobile/web2/index.html†L1-L116】【F:entertainment-planner-api/apps/web-mobile/web2/app1.js†L1-L80】

### Data & Signals

* Domain schemas defined in `apps.places.schemas`. `ComposeRequest/Response`, `Rail`, and `PlaceCard` encode the API contract for rails and cards; fields include vibes, signals (e.g., `dateworthy`, `novelty_score`), and metadata used for romance/chill detection.【F:entertainment-planner-api/apps/places/schemas/vibes.py†L74-L165】
* `/api/compose` loads additional heuristics from `config/extraordinary.yml` (fallback embedded) and drives vibe/category rails from synonyms, ranking, and slotting services.【F:entertainment-planner-api/apps/api/routes/compose.py†L1-L120】

## Infrastructure & Deploy Hooks

* **Docker**: Python 3.11 slim, installs pinned requirements, runs Uvicorn on port 8000 as non-root user.【F:Dockerfile†L1-L24】
* **Fly.io**: `fly.toml` targets autoscaling app `entertainment-planner` in `sin` region with `/health` implied, port 8000, scale-to-zero enabled.【F:fly.toml†L1-L24】
* No `.replit` yet; Replit recipe will need to mirror the Docker/Uvicorn command.

## Health & Observability Gaps

* `/health` endpoint depends on DB connectivity, violating constant-time health check requirement for autoscaling readiness.【F:entertainment-planner-api/apps/api/routes/health.py†L16-L55】
* Background MV refresh task in `main.py` may fail silently (logs with `print`).【F:entertainment-planner-api/apps/api/main.py†L37-L55】
* Logging defaults to root logger; module loggers exist but global level/config not pinned.

## Pending Investigation Threads

1. **Rails Semantics** – Need to validate `/api/rails` (compose) for Acceptance Case A to ensure Chill/Cinema/Romantic rails are emitted without food duplicates.
2. **Health Check Hardening** – Introduce `/health` that short-circuits before DB and keep `/health/db` for deep diagnostics.
3. **Replit Recipe** – Provide `.replit` or README run block aligning with `uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT` and pinned requirements.
4. **Config Hygiene** – Replace placeholder secrets in repo (`google_maps_api_key` defaults) and author authoritative `.env.example`.

This baseline will guide the subsequent cleanup phases (environment locking, smoke tests, deploy automation).
