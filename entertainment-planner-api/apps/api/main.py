from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import logging
import os
from sqlalchemy import text

from apps.api.routes import (
    health,
    places,
    recommend,
    admin_places,
    parse,
    compose,
    feedback,
    config,
)
from apps.core.db import engine

# Create FastAPI app
app = FastAPI(
    title="Entertainment Planner API",
    description="API for entertainment places search and route recommendations",
    version="1.0.0"
)

# CORS — чтобы фронт видел X-Rails/X-Mode/X-Rails-Cache
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Rails", "X-Mode", "X-Rails-Cache"],
)

# Include routers
app.include_router(health.router, prefix="/api")
app.include_router(places.router, prefix="/api", tags=["places"])
app.include_router(recommend.router, tags=["recommendations"])
app.include_router(admin_places.router, tags=["admin"])
app.include_router(parse.router, prefix="/api", tags=["parse"])
app.include_router(compose.router, prefix="/api", tags=["compose"])
app.include_router(feedback.router, prefix="/api", tags=["feedback"])
app.include_router(config.router, prefix="/api", tags=["config"])

# Mount static files for mobile app
app.mount("/", StaticFiles(directory="apps/web-mobile", html=True), name="mobile")

# Mount static files for web2 app
app.mount("/web2", StaticFiles(directory="apps/web-mobile/web2", html=True), name="web2")

logger = logging.getLogger(__name__)


@app.on_event("startup")
async def schedule_mv_refresh():
    logger.info(
        "startup complete", extra={"env": os.getenv("APP_ENV", "dev"), "port": os.getenv("PORT", "8000")}
    )

    async def worker():
        while True:
            try:
                with engine.connect() as c:
                    c.execute(text("SELECT epx.refresh_places_search_mv();"))
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("MV refresh loop error: %s", exc)
            await asyncio.sleep(300)  # 5 min
    asyncio.create_task(worker())

@app.get("/")
async def root():
    return {"message": "Entertainment Planner API", "version": "1.0.0"}


