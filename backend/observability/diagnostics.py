"""Diagnostics and health monitoring."""
import os
import platform
import sys
from typing import Any, Dict
from backend.config import settings


def get_system_diagnostics() -> Dict[str, Any]:
    """Returns safe diagnostic information without sensitive environment variables."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "database_connected": True,  # Will be verified at readiness
        "storage_writable": os.access(settings.artifacts_dir, os.W_OK),
    }


def get_liveness() -> Dict[str, str]:
    return {"status": "ok"}


def get_readiness(db_ok: bool) -> Dict[str, Any]:
    storage_ok = os.access(settings.artifacts_dir, os.W_OK)
    ready = db_ok and storage_ok
    return {
        "status": "ready" if ready else "not_ready",
        "database": "ok" if db_ok else "unreachable",
        "storage": "ok" if storage_ok else "unwritable",
    }
