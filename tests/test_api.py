"""Tests for TrainBench REST API endpoints."""
import asyncio
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from backend.api.main import app
from backend.persistence.database import init_db


@pytest.fixture(autouse=True)
async def prepare_database():
    await init_db()


@pytest.mark.asyncio
async def test_health_and_diagnostics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}
        assert "x-correlation-id" in res.headers

        # 2. Diagnostics
        diag = await client.get("/api/v1/diagnostics")
        assert diag.status_code == 200
        data = diag.json()
        assert data["app_name"] == "TrainBench"
        assert "python_version" in data


@pytest.mark.asyncio
async def test_project_and_run_lifecycle():
    transport = ASGITransport(app=app)
    proj_name = f"Benchmark Project {uuid.uuid4().hex[:6]}"
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Project
        p_res = await client.post("/api/v1/projects", json={
            "name": proj_name,
            "description": "Comparative evaluation project",
        })
        assert p_res.status_code == 201
        project = p_res.json()
        project_id = project["id"]
        assert project["name"] == proj_name

        # 2. List Projects
        list_res = await client.get("/api/v1/projects")
        assert list_res.status_code == 200
        projects = list_res.json()
        assert any(p["id"] == project_id for p in projects)

        # 3. Create NumPy Regression Run
        run_payload = {
            "project_id": project_id,
            "name": "NumPy Baseline Run",
            "framework": "numpy",
            "task": "regression",
            "dataset": {
                "name": "synth_regression",
                "task_type": "regression",
                "n_samples": 200,
                "n_features": 4,
                "val_split": 0.2,
            },
            "model": {
                "architecture": "linear",
                "hidden_dims": [],
            },
            "hyperparameters": {
                "epochs": 10,
                "batch_size": 32,
                "learning_rate": 0.05,
                "optimizer": "sgd",
            },
            "seed": 42,
            "device": "cpu",
        }
        r_res = await client.post("/api/v1/runs", json=run_payload)
        assert r_res.status_code == 201
        run_data = r_res.json()
        run_id = run_data["id"]
        assert run_data["status"] in ("queued", "running")

        # Wait a moment for background worker
        await asyncio.sleep(1.0)

        # 4. Get Run Detail
        detail_res = await client.get(f"/api/v1/runs/{run_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["id"] == run_id
        assert detail["provenance"]["config_hash"] is not None

        # 5. Reproduce Run
        repro_res = await client.post(f"/api/v1/runs/{run_id}/reproduce")
        assert repro_res.status_code == 201
        repro_run = repro_res.json()
        assert repro_run["id"] != run_id

        # 6. Compare Runs
        comp_res = await client.post("/api/v1/runs/compare", json={
            "run_ids": [run_id, repro_run["id"]]
        })
        assert comp_res.status_code == 200
        comparison = comp_res.json()
        assert comparison["compatible"] is True
        assert len(comparison["runs"]) == 2
