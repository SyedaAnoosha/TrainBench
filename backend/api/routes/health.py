"""Health and readiness diagnostic routes."""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from backend.config import settings
from backend.observability.diagnostics import get_liveness, get_readiness, get_system_diagnostics
from backend.persistence.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Liveness probe."""
    return get_liveness()


@router.get("/ready")
async def readiness_check(response: Response, db: AsyncSession = Depends(get_db)):
    """Readiness probe checking DB connectivity and storage access."""
    db_ok = False
    try:
        res = await db.execute(text("SELECT 1"))
        db_ok = res.scalar() == 1
    except Exception:
        db_ok = False

    result = get_readiness(db_ok=db_ok)
    if result["status"] != "ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/diagnostics")
async def diagnostics():
    """Safe system diagnostic metadata."""
    if not settings.expose_diagnostics:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return get_system_diagnostics()
