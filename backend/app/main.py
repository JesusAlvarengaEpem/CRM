"""
CRM Unificado EPEM — FastAPI Application
Stage 1 — ETL + Migration
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base
from app.routers import health as health_module
from app.routers import auth, dashboard, etl_routes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("crm.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown events."""
    # Startup: ensure DB tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")

    # Start ETL scheduler
    try:
        from etl.scheduler import start_scheduler
        start_scheduler()
        logger.info("ETL scheduler started")
    except Exception as e:
        logger.warning(f"ETL scheduler not started (DB may not be ready): {e}")

    yield

    # Shutdown
    from etl.scheduler import stop_scheduler
    stop_scheduler()
    await engine.dispose()


app = FastAPI(
    title="CRM Unificado EPEM",
    description="Dashboard de CRM unificado — Botmaker + Manual",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_module.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(etl_routes.router)
try:
    from app.routers import botmaker
    app.include_router(botmaker.router)
except ImportError:
    pass


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Log unhandled exceptions with full traceback."""
    import traceback
    logger.error(f"Unhandled exception on {request.method} {request.url.path}:\n{traceback.format_exc()}")
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {str(exc)[:500]}"},
    )


@app.get("/")
async def root():
    return {
        "app": "CRM Unificado EPEM",
        "version": "0.1.0",
        "status": "operational",
    }
