"""Dataset upload, management, validation, and lifecycle endpoints."""
import json
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.routes.projects import get_current_user_id
from backend.api.schemas import DatasetColumnInfo, DatasetResponse
from backend.artifacts.storage import storage_service
from backend.config import settings
from backend.domain.dataset_inspector import inspect_dataset_bytes
from backend.domain.policies import enforce_dataset_ownership, enforce_project_ownership
from backend.persistence.database import get_db
from backend.persistence.repositories import DatasetRepository, ProjectRepository
from backend.persistence.schema import DatasetModel

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _to_dataset_response(model: DatasetModel) -> DatasetResponse:
    parsed = json.loads(model.columns_json)
    cols = parsed.get("columns", [])
    raw_details = parsed.get("column_details", [])
    details = [
        DatasetColumnInfo(
            name=d["name"],
            dtype=d["dtype"],
            unique_count=d.get("unique_count", 0),
            sample_values=d.get("sample_values", []),
        )
        for d in raw_details
    ]
    return DatasetResponse(
        id=model.id,
        project_id=model.project_id,
        owner_id=model.owner_id,
        original_filename=model.original_filename,
        format=model.format,
        size_bytes=model.size_bytes,
        checksum=model.checksum,
        validation_status=model.validation_status,
        columns=cols,
        column_details=details,
        row_count=model.row_count,
        created_at=model.created_at,
    )


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Uploads, validates, hashes, and stores a local dataset file for a project."""
    # 1. Verify project exists and belongs to current user
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    enforce_project_ownership(project.owner_id, user_id)

    # 2. Check filename and format
    filename = file.filename or "dataset.csv"
    lower_name = filename.lower()
    ext_matched = None
    for fmt in settings.allowed_dataset_formats:
        if lower_name.endswith(f".{fmt}"):
            ext_matched = fmt
            break

    if not ext_matched:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file format for '{filename}'. Allowed formats: {', '.join(settings.allowed_dataset_formats)}",
        )

    # 3. Read content with size bounding
    raw_bytes = await file.read()
    if len(raw_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty",
        )
    if len(raw_bytes) > settings.max_dataset_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file ({len(raw_bytes)} bytes) exceeds maximum limit of {settings.max_dataset_size_bytes} bytes",
        )

    # 4. Inspect content and schema
    inspection = inspect_dataset_bytes(raw_bytes, filename)
    if not inspection.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dataset validation failed: {inspection.error}",
        )

    # 5. Check duplicate checksum in this project (idempotent / deduplication)
    import hashlib
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    dataset_repo = DatasetRepository(db)
    existing = await dataset_repo.get_by_project_and_checksum(project_id, checksum)
    if existing:
        return _to_dataset_response(existing)

    # 6. Store file safely in storage
    dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
    safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    storage_key = f"datasets/{project_id}/{dataset_id}_{safe_filename}"

    try:
        saved_checksum, size_bytes = storage_service.save_bytes(storage_key, raw_bytes)
        columns_payload = json.dumps({
            "columns": inspection.columns,
            "column_details": [d.model_dump() for d in inspection.column_details],
        })

        dataset = await dataset_repo.create(
            dataset_id=dataset_id,
            project_id=project_id,
            owner_id=user_id,
            original_filename=filename,
            format=inspection.format,
            size_bytes=size_bytes,
            checksum=saved_checksum,
            storage_key=storage_key,
            columns_json=columns_payload,
            row_count=inspection.row_count,
            validation_status="validated",
        )
        await db.commit()
        return _to_dataset_response(dataset)

    except Exception as exc:
        # Clean up stored bytes on failure
        storage_service.delete_file(storage_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to persist dataset: {str(exc)}",
        )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Retrieves dataset metadata and validation status."""
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id)
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    enforce_dataset_ownership(dataset.owner_id, user_id)
    return _to_dataset_response(dataset)


@router.get("", response_model=List[DatasetResponse])
async def list_datasets(
    project_id: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Lists validated datasets for a project."""
    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    enforce_project_ownership(project.owner_id, user_id)

    dataset_repo = DatasetRepository(db)
    datasets = await dataset_repo.list_by_project(project_id=project_id, limit=limit, offset=offset)
    return [_to_dataset_response(d) for d in datasets]


@router.delete("/{dataset_id}", status_code=status.HTTP_200_OK)
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Deletes an unreferenced dataset. Rejects deletion if referenced by any run."""
    dataset_repo = DatasetRepository(db)
    dataset = await dataset_repo.get_by_id(dataset_id)
    if not dataset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    enforce_dataset_ownership(dataset.owner_id, user_id)

    # Check if any run references this dataset
    ref_count = await dataset_repo.count_references(dataset_id)
    if ref_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete dataset '{dataset.original_filename}': it is referenced by {ref_count} training run(s)",
        )

    # Delete storage file
    storage_service.delete_file(dataset.storage_key)

    # Delete database record
    await dataset_repo.delete(dataset_id)
    await db.commit()

    return {"deleted": True, "dataset_id": dataset_id}
