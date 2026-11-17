"""TrainBench FastAPI application entry point."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from backend.api.middleware import CorrelationIdMiddleware, RateLimitMiddleware
from backend.api.routes import artifacts, datasets, health, projects, runs
from backend.config import settings
from backend.observability.logging import logger
from backend.persistence.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    _enforce_safe_bind()
    logger.info("Initializing database schema...")
    await init_db()
    logger.info(f"{settings.app_name} v{settings.app_version} started successfully.")
    yield
    logger.info(f"{settings.app_name} shutting down.")


def _enforce_safe_bind() -> None:
    """Refuse to serve on a non-loopback address unless explicitly opted in."""
    import ipaddress

    host = settings.host.strip().lower()
    if host in ("localhost",):
        return
    try:
        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass  # hostname — treat as public
    if not settings.allow_public_bind:
        raise RuntimeError(
            f"Refusing to bind to non-loopback host '{settings.host}'. "
            "TrainBench has no authentication; set TRAINBENCH_ALLOW_PUBLIC_BIND=true "
            "to override (not recommended)."
        )
    logger.warning(f"Serving on non-loopback host '{settings.host}' with allow_public_bind=true — no authentication is enabled.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="ML Training & Experiment Management Platform",
        docs_url="/docs" if settings.expose_api_docs else None,
        redoc_url="/redoc" if settings.expose_api_docs else None,
        openapi_url="/openapi.json" if settings.expose_api_docs else None,
        lifespan=lifespan,
    )

    # Middleware (added in reverse order: last added is outermost)
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.rate_limit_per_minute)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "X-Response-Time-MS"],
    )

    # Include Routes
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(projects.router, prefix=settings.api_prefix)
    app.include_router(datasets.router, prefix=settings.api_prefix)
    app.include_router(runs.router, prefix=settings.api_prefix)
    app.include_router(artifacts.router, prefix=settings.api_prefix)

    # Mount compiled frontend if available
    dist_dir = settings.base_dir / "frontend" / "dist"
    if dist_dir.exists():
        app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # Don't intercept API routes or docs — return a real 404, not null.
            if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            # Resolve and confine to dist_dir to block path traversal (e.g. /%2e%2e/%2e%2e/...).
            dist_root = dist_dir.resolve()
            target = (dist_root / full_path).resolve()
            if target != dist_root and not target.is_relative_to(dist_root):
                return FileResponse(dist_root / "index.html")
            if target.exists() and target.is_file():
                return FileResponse(target)
            return FileResponse(dist_root / "index.html")

    return app


app = create_app()
