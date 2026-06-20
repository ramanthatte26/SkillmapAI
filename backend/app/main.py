"""
SkillMap AI — FastAPI Application Factory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This is the application entry point. It:
  1. Creates the FastAPI app with metadata for OpenAPI docs
  2. Configures CORS middleware
  3. Registers all API routers under /api/v1
  4. Adds global exception handlers for consistent error shapes
  5. Exposes a health-check endpoint

Run with:
    uvicorn app.main:app --reload --port 8000

Docs available at:
    http://localhost:8000/docs      (Swagger UI)
    http://localhost:8000/redoc     (ReDoc)
"""

print("Application starting...", flush=True)

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import auth, roadmaps, progress, videos, search, course_video

print("Routers loaded...", flush=True)

settings = get_settings()

# ── Logging ───────────────────────────────────────────────────────
# Configure logging once at module level so all app.* loggers
# inherit this configuration. In production, swap StreamHandler
# for a structured JSON logger (e.g. python-json-logger).
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler (replaces deprecated on_event).

    startup:  Log the app launch (DB table creation is handled by Alembic,
              NOT here — we never call Base.metadata.create_all() in production)
    shutdown: Any cleanup (DB pool, cache connections) would go here.
    """
    try:
        from app.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connected...", flush=True)
    except Exception as exc:
        print(f"Database connection failed: {exc}", flush=True)

    print("Application ready...", flush=True)
    yield
    print(f"[STOP] {settings.app_name} API shutting down...", flush=True)


# ── App Instance ──────────────────────────────────────────────────
app = FastAPI(
    title=f"{settings.app_name} API",
    description=(
        "Backend API for SkillMap AI — convert YouTube playlists into "
        "structured learning roadmaps with progress tracking and AI-generated notes."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── CORS Middleware ───────────────────────────────────────────────
# Must be added BEFORE routers so preflight OPTIONS requests are handled.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,   # required for httpOnly cookie support
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handlers ─────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catch-all for any unhandled exceptions — returns a generic 500.
    In production, this prevents stack traces from leaking to the client.
    """
    logger.exception("Unhandled exception in API request: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Please try again later."
        },
    )



# ── API Routers ───────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(roadmaps.router, prefix=API_PREFIX)
app.include_router(progress.router, prefix=API_PREFIX)
app.include_router(videos.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
app.include_router(course_video.router, prefix=API_PREFIX)

# Future routers (uncomment as implemented):
# from app.routers import users
# app.include_router(users.router, prefix=API_PREFIX)


# ── Health Check ──────────────────────────────────────────────────
@app.get(
    "/health",
    tags=["System"],
    summary="API health check",
    description="Returns OK when the API is running. Used by load balancers and monitoring.",
)
def health_check():
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "1.0.0",
        "environment": settings.app_env,
    }


@app.get("/", tags=["System"], include_in_schema=False)
def root():
    """Root redirect hint — useful during development."""
    return {"message": f"Welcome to {settings.app_name} API. Visit /docs for documentation."}
