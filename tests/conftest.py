"""Pytest configuration: isolate the test suite from any developer .env.

Must run before backend modules are imported, since the SQLAlchemy engine is
created at import time from settings.database_url. Uses a throwaway SQLite file
so tests never touch a real database.
"""
import os
import tempfile

os.environ["TRAINBENCH_DATABASE_URL"] = (
    f"sqlite+aiosqlite:///{tempfile.mkdtemp(prefix='trainbench-test-')}/test.db"
)

import pytest
from backend.api.middleware import RateLimitMiddleware
from backend.persistence.database import init_db


@pytest.fixture(autouse=True)
async def setup_test_environment():
    await init_db()
    RateLimitMiddleware.reset()
    yield
    RateLimitMiddleware.reset()
