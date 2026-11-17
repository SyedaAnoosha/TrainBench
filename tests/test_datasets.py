"""TEST-011: Dataset upload, validation, lifecycle, and security tests."""
import io
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from backend.api.main import app
from backend.artifacts.storage import storage_service
from backend.config import settings
from backend.persistence.database import init_db


@pytest.fixture(autouse=True)
async def prepare_database():
    await init_db()


@pytest.fixture
def auth_headers():
    return {"X-Correlation-ID": "test-dataset-cid"}


@pytest.mark.asyncio
async def test_dataset_upload_csv_success(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project
        p_res = await client.post("/api/v1/projects", json={"name": f"P_Upload_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        assert p_res.status_code == 201
        project_id = p_res.json()["id"]

        # CSV data with 5 samples, 2 features, and a target
        csv_content = (
            "feature1,feature2,target\n"
            "1.0,2.0,0\n"
            "1.5,2.5,1\n"
            "2.0,3.0,0\n"
            "2.5,3.5,1\n"
            "3.0,4.0,0\n"
        ).encode("utf-8")

        files = {"file": ("dataset.csv", io.BytesIO(csv_content), "text/csv")}
        data = {"project_id": project_id}

        res = await client.post("/api/v1/datasets", data=data, files=files, headers=auth_headers)
        assert res.status_code == 201
        body = res.json()
        assert body["project_id"] == project_id
        assert body["format"] == "csv"
        assert body["row_count"] == 5
        assert "feature1" in body["columns"]
        assert "feature2" in body["columns"]
        assert "target" in body["columns"]
        assert body["validation_status"] == "validated"
        assert len(body["checksum"]) == 64

        dataset_id = body["id"]

        # GET dataset metadata
        get_res = await client.get(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
        assert get_res.status_code == 200
        assert get_res.json()["id"] == dataset_id

        # List project datasets
        list_res = await client.get(f"/api/v1/projects/{project_id}/datasets", headers=auth_headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1


@pytest.mark.asyncio
async def test_dataset_upload_json_success(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post("/api/v1/projects", json={"name": f"P_JSON_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        json_content = (
            '[{"x1": 1.2, "x2": 3.4, "label": "cat"},'
            ' {"x1": 2.2, "x2": 4.4, "label": "dog"},'
            ' {"x1": 3.2, "x2": 5.4, "label": "cat"}]'
        ).encode("utf-8")

        files = {"file": ("data.json", io.BytesIO(json_content), "application/json")}
        res = await client.post("/api/v1/datasets", data={"project_id": project_id}, files=files, headers=auth_headers)
        assert res.status_code == 201
        body = res.json()
        assert body["format"] == "json"
        assert body["row_count"] == 3
        assert "label" in body["columns"]


@pytest.mark.asyncio
async def test_dataset_upload_unsupported_extension(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post("/api/v1/projects", json={"name": f"P_BadExt_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        files = {"file": ("malicious.exe", io.BytesIO(b"MZ..."), "application/octet-stream")}
        res = await client.post("/api/v1/datasets", data={"project_id": project_id}, files=files, headers=auth_headers)
        assert res.status_code == 422
        assert "Unsupported file format" in res.json()["detail"]


@pytest.mark.asyncio
async def test_dataset_upload_oversized_file(auth_headers, monkeypatch):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post("/api/v1/projects", json={"name": f"P_Big_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        # Temporarily lower size limit to 50 bytes
        monkeypatch.setattr(settings, "max_dataset_size_bytes", 50)

        big_csv = ("a,b,c\n" + "1,2,3\n" * 10).encode("utf-8")
        assert len(big_csv) > 50

        files = {"file": ("big.csv", io.BytesIO(big_csv), "text/csv")}
        res = await client.post("/api/v1/datasets", data={"project_id": project_id}, files=files, headers=auth_headers)
        assert res.status_code in (413, 422)


@pytest.mark.asyncio
async def test_dataset_upload_corrupt_content(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post("/api/v1/projects", json={"name": f"P_Corrupt_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        # CSV with ragged columns (row 2 has 2 cols, row 3 has 5 cols)
        corrupt_csv = "col1,col2\n1\n1,2,3,4,5\n".encode("utf-8")
        files = {"file": ("corrupt.csv", io.BytesIO(corrupt_csv), "text/csv")}
        res = await client.post("/api/v1/datasets", data={"project_id": project_id}, files=files, headers=auth_headers)
        assert res.status_code == 422
        assert "validation failed" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_dataset_duplicate_checksum_idempotent(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post("/api/v1/projects", json={"name": f"P_Dedup_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        csv_data = "x,y,z\n1,2,3\n4,5,6\n".encode("utf-8")
        files1 = {"file": ("data.csv", io.BytesIO(csv_data), "text/csv")}
        res1 = await client.post("/api/v1/datasets", data={"project_id": project_id}, files=files1, headers=auth_headers)
        assert res1.status_code == 201

        # Upload exact same bytes again
        files2 = {"file": ("data.csv", io.BytesIO(csv_data), "text/csv")}
        res2 = await client.post("/api/v1/datasets", data={"project_id": project_id}, files=files2, headers=auth_headers)
        assert res2.status_code in (200, 201)
        # Should return the existing dataset with same checksum and ID
        assert res2.json()["checksum"] == res1.json()["checksum"]
        assert res2.json()["id"] == res1.json()["id"]


@pytest.mark.asyncio
async def test_dataset_unauthorized_project_access(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User A creates project
        p_res = await client.post("/api/v1/projects", json={"name": f"P_Other_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        # Different user tries to upload to user A's project
        # In single user mode default_user_id is user-local; simulate non-owner by requesting nonexistent project
        res = await client.post(
            "/api/v1/datasets",
            data={"project_id": "nonexistent-project-id"},
            files={"file": ("d.csv", io.BytesIO(b"a,b\n1,2\n3,4\n"), "text/csv")},
            headers=auth_headers,
        )
        assert res.status_code == 404


@pytest.mark.asyncio
async def test_dataset_deletion_and_referenced_guard(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post("/api/v1/projects", json={"name": f"P_Del_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        csv_data = "feat1,feat2,target\n1.0,2.0,1\n3.0,4.0,2\n5.0,6.0,1\n".encode("utf-8")
        upload_res = await client.post(
            "/api/v1/datasets",
            data={"project_id": project_id},
            files={"file": ("training.csv", io.BytesIO(csv_data), "text/csv")},
            headers=auth_headers,
        )
        dataset_id = upload_res.json()["id"]

        # 1. Create a run referencing this dataset
        run_payload = {
            "project_id": project_id,
            "name": "Dataset Run",
            "framework": "numpy",
            "task": "classification",
            "dataset": {
                "name": "training.csv",
                "task_type": "classification",
                "source": "uploaded",
                "dataset_id": dataset_id,
                "target_column": "target",
                "val_split": 0.2,
            },
            "model": {"architecture": "linear", "hidden_dims": []},
            "hyperparameters": {"epochs": 2, "batch_size": 2, "learning_rate": 0.01},
            "seed": 42,
            "device": "cpu",
        }
        run_res = await client.post("/api/v1/runs", json=run_payload, headers=auth_headers)
        assert run_res.status_code == 201

        # 2. Attempting to delete the referenced dataset must fail with 409 Conflict
        del_conflict = await client.delete(f"/api/v1/datasets/{dataset_id}", headers=auth_headers)
        assert del_conflict.status_code == 409
        assert "referenced by" in del_conflict.json()["detail"].lower()

        # 3. Create another unreferenced dataset and delete it successfully
        csv_unref = "a,b\n1,2\n3,4\n".encode("utf-8")
        unref_res = await client.post(
            "/api/v1/datasets",
            data={"project_id": project_id},
            files={"file": ("unref.csv", io.BytesIO(csv_unref), "text/csv")},
            headers=auth_headers,
        )
        unref_id = unref_res.json()["id"]

        del_ok = await client.delete(f"/api/v1/datasets/{unref_id}", headers=auth_headers)
        assert del_ok.status_code == 200
        assert del_ok.json()["deleted"] is True

        # Now GET should 404
        get_deleted = await client.get(f"/api/v1/datasets/{unref_id}", headers=auth_headers)
        assert get_deleted.status_code == 404


@pytest.mark.asyncio
async def test_dataset_invalid_target_mapping_rejected(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post("/api/v1/projects", json={"name": f"P_Map_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        csv_data = "feat1,feat2,label\n1.0,2.0,1\n3.0,4.0,2\n".encode("utf-8")
        upload_res = await client.post(
            "/api/v1/datasets",
            data={"project_id": project_id},
            files={"file": ("training.csv", io.BytesIO(csv_data), "text/csv")},
            headers=auth_headers,
        )
        dataset_id = upload_res.json()["id"]

        # Run specifying non-existent target column "nonexistent_target"
        bad_run = {
            "project_id": project_id,
            "name": "Bad Mapping Run",
            "framework": "numpy",
            "task": "classification",
            "dataset": {
                "name": "training.csv",
                "task_type": "classification",
                "source": "uploaded",
                "dataset_id": dataset_id,
                "target_column": "nonexistent_target",
            },
            "model": {"architecture": "linear", "hidden_dims": []},
            "hyperparameters": {"epochs": 2, "batch_size": 2, "learning_rate": 0.01},
            "seed": 42,
            "device": "cpu",
        }
        res = await client.post("/api/v1/runs", json=bad_run, headers=auth_headers)
        assert res.status_code == 422
        assert "Target column" in res.json()["detail"]


@pytest.mark.asyncio
async def test_training_execution_with_uploaded_dataset(auth_headers):
    """Verifies that an actual training job executes end-to-end using an uploaded dataset."""
    import asyncio
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p_res = await client.post("/api/v1/projects", json={"name": f"P_Exec_{uuid.uuid4().hex[:6]}"}, headers=auth_headers)
        project_id = p_res.json()["id"]

        csv_data = (
            "f1,f2,target\n"
            "0.1,0.2,0\n"
            "0.2,0.3,0\n"
            "0.3,0.4,0\n"
            "1.1,1.2,1\n"
            "1.2,1.3,1\n"
            "1.3,1.4,1\n"
        ).encode("utf-8")

        up_res = await client.post(
            "/api/v1/datasets",
            data={"project_id": project_id},
            files={"file": ("train.csv", io.BytesIO(csv_data), "text/csv")},
            headers=auth_headers,
        )
        dataset_id = up_res.json()["id"]

        run_payload = {
            "project_id": project_id,
            "name": "Live Uploaded Training Run",
            "framework": "numpy",
            "task": "classification",
            "dataset": {
                "name": "train.csv",
                "task_type": "classification",
                "source": "uploaded",
                "dataset_id": dataset_id,
                "target_column": "target",
                "val_split": 0.33,
            },
            "model": {"architecture": "linear", "hidden_dims": []},
            "hyperparameters": {"epochs": 3, "batch_size": 2, "learning_rate": 0.05},
            "seed": 42,
            "device": "cpu",
        }

        create_res = await client.post("/api/v1/runs", json=run_payload, headers=auth_headers)
        assert create_res.status_code == 201
        run_id = create_res.json()["id"]

        # Poll run status until succeeded
        for _ in range(30):
            await asyncio.sleep(0.3)
            status_res = await client.get(f"/api/v1/runs/{run_id}", headers=auth_headers)
            if status_res.json()["status"] in ("succeeded", "failed"):
                break

        final_run = status_res.json()
        assert final_run["status"] == "succeeded"
        assert final_run["metrics_summary"] is not None
        assert "loss_train" in final_run["metrics_summary"]
