"""Artifact retrieval and safe download endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.routes.projects import get_current_user_id
from backend.artifacts.storage import storage_service
from backend.domain.policies import enforce_run_ownership
from backend.persistence.database import get_db
from backend.persistence.repositories import ArtifactRepository, RunRepository

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}/download")
async def download_artifact(
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    art_repo = ArtifactRepository(db)
    artifact = await art_repo.get_by_id(artifact_id)
    if not artifact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact record not found")

    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(artifact.run_id, load_details=False)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated run not found")

    enforce_run_ownership(run.created_by, user_id)

    file_path = storage_service.get_file_path(artifact.storage_key)

    return FileResponse(
        path=file_path,
        filename=artifact.filename,
        media_type="application/octet-stream",
    )
