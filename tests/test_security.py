"""Security regression tests: traversal, auth, validation caps, rate limiting."""
import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app
from backend.artifacts.storage import storage_service
from backend.config import settings
from backend.domain.models import (
    DatasetConfig,
    Framework,
    Hyperparameters,
    ModelConfig,
    RunConfiguration,
    TaskType,
)
from backend.domain.validation import validate_run_configuration


def make_config(**overrides) -> RunConfiguration:
    kwargs = dict(
        project_id="p1",
        name="test run",
        framework=Framework.NUMPY,
        task=TaskType.REGRESSION,
        dataset=DatasetConfig(name="d", task_type=TaskType.REGRESSION, n_samples=50),
        model=ModelConfig(architecture="linear", hidden_dims=[]),
        hyperparameters=Hyperparameters(epochs=1, batch_size=8, learning_rate=0.01),
        seed=1,
    )
    kwargs.update(overrides)
    return RunConfiguration(**kwargs)


# ---------- Storage path containment ----------

def test_storage_rejects_prefix_confusion_traversal():
    for key in ("../artifacts_evil/evil.pt", "sub/../../artifacts_evil/evil.pt"):
        with pytest.raises(Exception):
            storage_service._resolve_safe_path(key)


def test_storage_allows_normal_key():
    p = storage_service._resolve_safe_path("my run/checkpoint.pt")
    assert "artifacts" in str(p)


# ---------- Run name / model validation ----------

def test_run_name_with_path_separator_rejected():
    for bad in ("../evil", "a/b", "a\\b", ".."):
        res = validate_run_configuration(make_config(name=bad))
        assert not res.is_valid, f"name {bad!r} should be rejected"


def test_hidden_dims_length_capped():
    cfg = make_config(
        framework=Framework.PYTORCH,
        model=ModelConfig(architecture="mlp", hidden_dims=[8] * 17),
        dataset=DatasetConfig(name="d", task_type=TaskType.CLASSIFICATION, n_samples=50, n_classes=2),
        task=TaskType.CLASSIFICATION,
    )
    res = validate_run_configuration(cfg)
    assert not res.is_valid


def test_dataset_size_product_capped():
    cfg = make_config(
        dataset=DatasetConfig(name="d", task_type=TaskType.REGRESSION, n_samples=100000, n_features=500),
    )
    res = validate_run_configuration(cfg)
    assert not res.is_valid


# ---------- API-level tests ----------

@pytest.mark.asyncio
async def test_spa_catchall_blocks_traversal():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/%2e%2e/%2e%2e/backend/config.py")
        assert res.status_code == 200
        assert b"class Settings" not in res.content
        assert b"<!doctype" in res.content.lower() or b"<div" in res.content

        res2 = await client.get("/api/v1/nonexistent-route")
        assert res2.status_code == 404


@pytest.mark.asyncio
async def test_api_key_auth_enforced_when_configured():
    transport = ASGITransport(app=app)
    original = settings.api_key
    settings.api_key = "test-secret-key"
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/projects")
            assert res.status_code == 401

            res = await client.get("/api/v1/projects", headers={"X-API-Key": "wrong"})
            assert res.status_code == 401

            res = await client.get("/api/v1/projects", headers={"X-API-Key": "test-secret-key"})
            assert res.status_code == 200

            res = await client.get(
                "/api/v1/projects", headers={"Authorization": "Bearer test-secret-key"}
            )
            assert res.status_code == 200
    finally:
        settings.api_key = original


@pytest.mark.asyncio
async def test_run_creation_rejects_traversal_name():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p = await client.post("/api/v1/projects", json={"name": f"sec-proj-{id(client)}"})
        assert p.status_code == 201
        project_id = p.json()["id"]

        res = await client.post("/api/v1/runs", json={
            "project_id": project_id,
            "name": "../evil",
            "framework": "numpy",
            "task": "regression",
            "dataset": {"name": "d", "task_type": "regression", "n_samples": 50},
            "model": {"architecture": "linear", "hidden_dims": []},
            "hyperparameters": {"epochs": 1, "batch_size": 8, "learning_rate": 0.01},
            "seed": 1,
            "device": "cpu",
        })
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_concurrency_cap_returns_429():
    transport = ASGITransport(app=app)
    original = settings.max_concurrent_runs
    settings.max_concurrent_runs = 0
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            p = await client.post("/api/v1/projects", json={"name": f"cap-proj-{id(client)}"})
            assert p.status_code == 201
            res = await client.post("/api/v1/runs", json={
                "project_id": p.json()["id"],
                "name": "cap test",
                "framework": "numpy",
                "task": "regression",
                "dataset": {"name": "d", "task_type": "regression", "n_samples": 50},
                "model": {"architecture": "linear", "hidden_dims": []},
                "hyperparameters": {"epochs": 1, "batch_size": 8, "learning_rate": 0.01},
                "seed": 1,
                "device": "cpu",
            })
            assert res.status_code == 429
    finally:
        settings.max_concurrent_runs = original


@pytest.mark.asyncio
async def test_write_rate_limit():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        codes = []
        for i in range(35):
            res = await client.post("/api/v1/projects", json={"name": f"rl-{i}"})
            codes.append(res.status_code)
        assert 429 in codes
        # GETs are never rate limited
        assert (await client.get("/api/v1/health")).status_code == 200
