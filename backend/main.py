"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from core.config import get_settings
from core.logging import setup_logging, get_logger
from core.state_manager import state_manager
from api.routes import router

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.schemas import HealthResponse


# ─── Lifespan ────────────────────────────────────────────────

async def cleanup_task():
    """Background task to clean expired sessions."""
    while True:
        try:
            await asyncio.sleep(300)  # Every 5 minutes
            cleaned = await state_manager.cleanup_expired()
            if cleaned > 0:
                logger.info("cleanup_completed", sessions_cleaned=cleaned)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("cleanup_error", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    settings = get_settings()

    # Setup logging
    setup_logging()
    global logger
    logger = get_logger("main")

    # Create directories
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)

    logger.info(
        "server_starting",
        cors_origins=settings.cors_origin_list,
        max_file_size_mb=settings.max_file_size_mb,
        log_level=settings.log_level,
    )

    # Start cleanup task
    cleanup = asyncio.create_task(cleanup_task())

    # Sentry (optional)
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1)
            logger.info("sentry_initialized")
        except ImportError:
            logger.warning("sentry_sdk_not_installed")

    yield

    # Shutdown
    cleanup.cancel()
    try:
        await cleanup
    except asyncio.CancelledError:
        pass
    logger.info("server_shutdown")


# ─── App ─────────────────────────────────────────────────────

logger = get_logger("main")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="DataCleaner AI",
    description="AI-powered data cleaning and exploratory data analysis",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Routes
app.include_router(router)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
    )


# ─── Init files ──────────────────────────────────────────────

# Create __init__.py files for proper imports
for pkg in ["core", "api", "agents", "tools"]:
    init_path = Path(__file__).parent / pkg / "__init__.py"
    init_path.parent.mkdir(parents=True, exist_ok=True)
    if not init_path.exists():
        init_path.write_text("")
