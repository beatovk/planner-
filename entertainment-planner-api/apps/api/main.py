import logging
from fastapi import FastAPI

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
from sqlalchemy import text
from apps.api.routes import health, places, recommend, admin_places, parse, compose, feedback, config
from apps.core.config import settings
from apps.core.db import engine, DB_URL

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
app.include_router(health.router, prefix="/api", tags=["health"])
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

@app.on_event("startup")
async def schedule_mv_refresh():
    async def worker():
        while True:
            try:
                with engine.connect() as c:
                    c.execute(text("SELECT epx.refresh_places_search_mv();"))
            except Exception:
                logger.exception("[MV refresh] error")
            await asyncio.sleep(300)  # 5 min
    asyncio.create_task(worker())

@app.get("/")
async def root():
    return {"message": "Entertainment Planner API", "version": "1.0.0"}


@app.get("/health/db")
def health_db():
    """Database health check endpoint for monitoring and deployment."""
    try:
        with engine.connect() as c:
            from sqlalchemy import text
            # Test basic connectivity
            c.execute(text("SELECT 1")).scalar()
            
            # Get places count for additional verification
            places_count = c.execute(text("SELECT COUNT(*) FROM places")).scalar()
            # MV age (seconds since last refresh)
            age_seconds = c.execute(text("""
                SELECT EXTRACT(EPOCH FROM (now() - refreshed_at))::int
                FROM epx.mv_refresh_heartbeat
                WHERE mv_name = 'places_search_mv'
            """)).scalar()
            
        return {
            "ok": True,
            "driver": "postgresql",
            "places_count": places_count,
            "dsn": DB_URL.split('@')[-1] if '@' in DB_URL else "masked",
            "mv_age_seconds": age_seconds
        }
    except Exception as e:
        return {
            "ok": False, 
            "error": str(e),
            "driver": "postgresql",
            "dsn": DB_URL.split('@')[-1] if '@' in DB_URL else "masked",
        }
