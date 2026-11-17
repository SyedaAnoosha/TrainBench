"""Project management endpoints."""
import hmac
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.schemas import DatasetResponse, ProjectCreateRequest, ProjectResponse
from backend.config import settings
from backend.domain.policies import enforce_project_ownership
from backend.persistence.database import get_db
from backend.persistence.repositories import AuditEventRepository, ProjectRepository
from backend.persistence.schema import RunModel

router = APIRouter(prefix="/projects", tags=["projects"])


def get_current_user_id(request: Request) -> str:
    # Single-user local mode uses settings.default_user_id. When TRAINBENCH_API_KEY
    # is configured, requests must authenticate with it (shared-secret mode).
    if settings.api_key:
        provided = request.headers.get("X-API-Key", "")
        auth = request.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if not hmac.compare_digest(provided or token, settings.api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API key",
            )
    return settings.default_user_id


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    req: ProjectCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ProjectRepository(db)
    project = await repo.create(name=req.name, description=req.description, owner_id=user_id)
    audit_repo = AuditEventRepository(db)
    await audit_repo.log_event(actor=user_id, action="create_project", resource=f"project:{project.id}")
    await db.commit()
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        run_count=0,
    )


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ProjectRepository(db)
    projects = await repo.list_by_owner(owner_id=user_id, limit=limit, offset=offset)

    responses = []
    for p in projects:
        # Count runs for each project
        count_stmt = select(func.count(RunModel.id)).where(RunModel.project_id == p.id)
        count_res = await db.execute(count_stmt)
        run_count = count_res.scalar() or 0
        responses.append(
            ProjectResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                owner_id=p.owner_id,
                created_at=p.created_at,
                updated_at=p.updated_at,
                run_count=run_count,
            )
        )
    return responses


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    enforce_project_ownership(project.owner_id, user_id)

    count_stmt = select(func.count(RunModel.id)).where(RunModel.project_id == project.id)
    count_res = await db.execute(count_stmt)
    run_count = count_res.scalar() or 0

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        run_count=run_count,
    )


@router.get("/{project_id}/datasets", response_model=List[DatasetResponse])
async def list_project_datasets(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """API-011: Lists datasets owned by the project with bounded pagination."""
    repo = ProjectRepository(db)
    project = await repo.get_by_id(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    enforce_project_ownership(project.owner_id, user_id)

    from backend.api.routes.datasets import _to_dataset_response
    from backend.persistence.repositories import DatasetRepository

    ds_repo = DatasetRepository(db)
    datasets = await ds_repo.list_by_project(project_id=project_id, limit=limit, offset=offset)
    return [_to_dataset_response(d) for d in datasets]
