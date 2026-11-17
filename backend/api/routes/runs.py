"""Run management, submission, monitoring, cancellation, reproduction, and comparison."""
import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.routes.projects import get_current_user_id
from backend.api.schemas import (
    ArtifactResponse,
    ComparisonRequest,
    ComparisonResponse,
    MetricFilterResponse,
    RunCreateRequest,
    RunDetailResponse,
    RunEventResponse,
    RunSummaryResponse,
)
from backend.config import settings
from backend.domain.models import ArtifactKind, Framework, MetricPoint, RunConfiguration, RunStatus, TaskType
from backend.domain.policies import enforce_project_ownership, enforce_run_ownership
from backend.domain.provenance import compute_config_fingerprint, generate_provenance_record
from backend.domain.validation import validate_run_configuration
from backend.jobs.runner import execute_run_job, is_run_cancelled, request_cancellation
from backend.observability.logging import get_correlation_id
from backend.persistence.database import get_db
from backend.persistence.repositories import (
    ArtifactRepository,
    AuditEventRepository,
    DatasetRepository,
    MetricRepository,
    ProjectRepository,
    RunRepository,
)
from backend.persistence.schema import RunModel

router = APIRouter(prefix="/runs", tags=["runs"])

# In-memory idempotency store: Idempotency-Key -> run_id (single-process app).
_IDEMPOTENCY_KEYS: Dict[str, str] = {}
_IDEMPOTENCY_MAX = 1000


def build_run_summary(run: RunModel, metrics_summary: Optional[Dict[str, Any]] = None) -> RunSummaryResponse:
    primary = None
    if metrics_summary:
        # Choose primary metric (accuracy if classification, r2 or val_loss if regression)
        if "accuracy_val" in metrics_summary:
            primary = metrics_summary["accuracy_val"]
        elif "r2_score_val" in metrics_summary:
            primary = metrics_summary["r2_score_val"]
        elif "loss_val" in metrics_summary:
            primary = metrics_summary["loss_val"]
        elif "loss_train" in metrics_summary:
            primary = metrics_summary["loss_train"]

    return RunSummaryResponse(
        id=run.id,
        project_id=run.project_id,
        name=run.name,
        status=RunStatus(run.status),
        framework=Framework(run.framework),
        task=TaskType(run.task),
        created_at=run.created_at,
        duration_ms=run.duration_ms,
        primary_metric=primary,
    )


@router.post("", response_model=RunSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    req: RunCreateRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run_repo = RunRepository(db)

    # Idempotent replay: return the originally created run for a repeated key.
    if idempotency_key:
        existing_id = _IDEMPOTENCY_KEYS.get(idempotency_key)
        if existing_id:
            existing = await run_repo.get_by_id(existing_id, load_details=False)
            if existing:
                enforce_run_ownership(existing.created_by, user_id)
                return build_run_summary(existing)

    project_repo = ProjectRepository(db)
    project = await project_repo.get_by_id(req.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    enforce_project_ownership(project.owner_id, user_id)

    # 1. Validation
    run_config = RunConfiguration(
        project_id=req.project_id,
        name=req.name,
        framework=req.framework,
        task=req.task,
        dataset=req.dataset,
        model=req.model,
        hyperparameters=req.hyperparameters,
        seed=req.seed,
        device=req.device,
        tags=req.tags,
    )

    validation_result = validate_run_configuration(run_config)
    if not validation_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=validation_result.to_dict(),
        )

    # 1.1 Verify dataset if referencing an uploaded dataset
    dataset_checksum = None
    if run_config.dataset.dataset_id:
        ds_repo = DatasetRepository(db)
        ds = await ds_repo.get_by_id(run_config.dataset.dataset_id)
        if not ds:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset {run_config.dataset.dataset_id} not found")
        if ds.project_id != req.project_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Dataset does not belong to this project")
        if ds.validation_status != "validated":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dataset is not validated")

        parsed_cols = json.loads(ds.columns_json).get("columns", [])
        if run_config.dataset.target_column not in parsed_cols:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Target column '{run_config.dataset.target_column}' not found in dataset columns: {parsed_cols}",
            )
        dataset_checksum = ds.checksum

    # 2. Provenance Fingerprints
    provenance = generate_provenance_record(run_config, known_dataset_checksum=dataset_checksum)
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    # 3. Persistence

    # Concurrency cap: each run occupies a worker for its full duration.
    active = await run_repo.count_active()
    if active >= settings.max_concurrent_runs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many active runs ({active}/{settings.max_concurrent_runs}). Wait for running jobs to finish.",
        )

    run = await run_repo.create_run(
        run_id=run_id,
        project_id=req.project_id,
        name=req.name,
        framework=req.framework.value,
        task=req.task.value,
        created_by=user_id,
        status=RunStatus.QUEUED.value,
    )

    await run_repo.save_config(
        run_id=run_id,
        config_json=json.dumps(run_config.model_dump()),
        seed=run_config.seed,
        config_hash=provenance["config_hash"],
        dataset_hash=provenance["dataset_hash"],
        dependency_fingerprint=json.dumps(provenance["dependencies"]),
        device=req.device.value,
        dataset_id=run_config.dataset.dataset_id,
    )

    await run_repo.add_event(run_id, "run_queued", {"provenance": provenance})
    audit_repo = AuditEventRepository(db)
    await audit_repo.log_event(actor=user_id, action="create_run", resource=f"run:{run_id}")
    await db.commit()

    if idempotency_key:
        if len(_IDEMPOTENCY_KEYS) >= _IDEMPOTENCY_MAX:
            _IDEMPOTENCY_KEYS.pop(next(iter(_IDEMPOTENCY_KEYS)))
        _IDEMPOTENCY_KEYS[idempotency_key] = run_id

    # 4. Asynchronous worker execution
    cid = get_correlation_id()
    background_tasks.add_task(execute_run_job, run_id, cid)

    return build_run_summary(run)


@router.get("", response_model=List[RunSummaryResponse])
async def list_runs(
    project_id: Optional[str] = Query(default=None),
    status_filter: Optional[RunStatus] = Query(default=None, alias="status"),
    framework: Optional[Framework] = Query(default=None),
    task: Optional[TaskType] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run_repo = RunRepository(db)
    metric_repo = MetricRepository(db)

    runs = await run_repo.list_runs(
        project_id=project_id,
        status=status_filter.value if status_filter else None,
        framework=framework.value if framework else None,
        task=task.value if task else None,
        owner_id=user_id,
        limit=limit,
        offset=offset,
    )

    results = []
    for r in runs:
        summary = await metric_repo.get_latest_summary(r.id)
        results.append(build_run_summary(r, summary))

    return results


@router.get("/{run_id}", response_model=RunDetailResponse)
async def get_run_detail(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run_repo = RunRepository(db)
    metric_repo = MetricRepository(db)

    run = await run_repo.get_by_id(run_id, load_details=True)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    enforce_run_ownership(run.created_by, user_id)

    metrics_summary = await metric_repo.get_latest_summary(run_id)

    config_dict = json.loads(run.config.config_json) if run.config else None
    provenance_dict = (
        {
            "config_hash": run.config.config_hash,
            "dataset_hash": run.config.dataset_hash,
            "dependencies": json.loads(run.config.dependency_fingerprint) if run.config.dependency_fingerprint else {},
            "seed": run.config.seed,
            "device": run.config.device,
        }
        if run.config
        else None
    )

    events_response = [
        RunEventResponse(
            id=e.id,
            event_type=e.event_type,
            payload=json.loads(e.payload) if e.payload else None,
            occurred_at=e.occurred_at,
        )
        for e in (run.events or [])
    ]

    artifacts_response = [
        ArtifactResponse(
            id=a.id,
            run_id=a.run_id,
            kind=ArtifactKind(a.kind),
            filename=a.filename,
            checksum=a.checksum,
            size_bytes=a.size_bytes,
            download_url=f"/api/v1/artifacts/{a.id}/download",
            created_at=a.created_at,
        )
        for a in (run.artifacts or [])
    ]

    return RunDetailResponse(
        id=run.id,
        project_id=run.project_id,
        name=run.name,
        parent_run_id=run.parent_run_id,
        status=RunStatus(run.status),
        framework=Framework(run.framework),
        task=TaskType(run.task),
        created_by=run.created_by,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
        terminal_error=run.terminal_error,
        terminal_error_code=run.terminal_error_code,
        config=config_dict,
        provenance=provenance_dict,
        events=events_response,
        artifacts=artifacts_response,
        metrics_summary=metrics_summary,
    )


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id, load_details=False)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    enforce_run_ownership(run.created_by, user_id)

    curr_status = RunStatus(run.status)
    if curr_status.is_terminal():
        return {"run_id": run_id, "status": curr_status.value, "message": "Run is already terminal"}

    # Signal worker to cancel
    request_cancellation(run_id)

    # If queued, can cancel immediately
    if curr_status == RunStatus.QUEUED:
        await run_repo.set_terminal_status(run_id, RunStatus.CANCELLED, error="Cancelled while queued")
        await run_repo.add_event(run_id, "run_cancelled")

    audit_repo = AuditEventRepository(db)
    await audit_repo.log_event(actor=user_id, action="cancel_run", resource=f"run:{run_id}")
    await db.commit()

    return {"run_id": run_id, "status": "cancellation_requested"}


@router.post("/{run_id}/reproduce", response_model=RunSummaryResponse, status_code=status.HTTP_201_CREATED)
async def reproduce_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Clones an existing run's immutable configuration and links child to parent."""
    run_repo = RunRepository(db)
    source_run = await run_repo.get_by_id(run_id, load_details=True)
    if not source_run or not source_run.config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source run configuration not found")

    enforce_run_ownership(source_run.created_by, user_id)

    config_dict = json.loads(source_run.config.config_json)
    run_config = RunConfiguration(**config_dict)

    # Create new child run
    child_run_id = f"run_{uuid.uuid4().hex[:12]}"
    child_run_name = f"{source_run.name} (Reproduction)"

    child_run = await run_repo.create_run(
        run_id=child_run_id,
        project_id=source_run.project_id,
        name=child_run_name,
        framework=source_run.framework,
        task=source_run.task,
        created_by=user_id,
        parent_run_id=source_run.id,
        status=RunStatus.QUEUED.value,
    )

    provenance = generate_provenance_record(run_config)
    await run_repo.save_config(
        run_id=child_run_id,
        config_json=source_run.config.config_json,
        seed=source_run.config.seed,
        config_hash=source_run.config.config_hash,
        dataset_hash=source_run.config.dataset_hash,
        dependency_fingerprint=source_run.config.dependency_fingerprint,
        device=source_run.config.device,
        dataset_id=source_run.config.dataset_id,
    )

    await run_repo.add_event(
        child_run_id,
        "run_reproduced",
        {"parent_run_id": source_run.id, "provenance": provenance},
    )
    audit_repo = AuditEventRepository(db)
    await audit_repo.log_event(actor=user_id, action="reproduce_run", resource=f"run:{child_run_id}")
    await db.commit()

    cid = get_correlation_id()
    background_tasks.add_task(execute_run_job, child_run_id, cid)

    return build_run_summary(child_run)


@router.get("/{run_id}/metrics", response_model=MetricFilterResponse)
async def get_run_metrics(
    run_id: str,
    names: Optional[List[str]] = Query(None),
    split: Optional[str] = Query(None),
    max_points: int = Query(default=1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    run_repo = RunRepository(db)
    run = await run_repo.get_by_id(run_id, load_details=False)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    enforce_run_ownership(run.created_by, user_id)

    metric_repo = MetricRepository(db)
    metric_models = await metric_repo.get_series(run_id=run_id, names=names, split=split, max_points=max_points)

    points = [
        MetricPoint(
            name=m.name,
            split=m.split,
            step=m.step,
            value=m.value,
            unit=m.unit,
        )
        for m in metric_models
    ]
    return MetricFilterResponse(run_id=run_id, points=points)


@router.post("/compare", response_model=ComparisonResponse)
async def compare_runs(
    req: ComparisonRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Compares multiple runs, validates task compatibility, and aligns metrics and hyperparameters."""
    run_repo = RunRepository(db)
    metric_repo = MetricRepository(db)

    runs_detail: List[RunDetailResponse] = []
    tasks_seen = set()

    for rid in req.run_ids:
        run = await run_repo.get_by_id(rid, load_details=True)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run {rid} not found")
        enforce_run_ownership(run.created_by, user_id)

        tasks_seen.add(run.task)
        summary = await metric_repo.get_latest_summary(rid)

        config_dict = json.loads(run.config.config_json) if run.config else None
        provenance_dict = (
            {
                "config_hash": run.config.config_hash,
                "dataset_hash": run.config.dataset_hash,
                "seed": run.config.seed,
                "device": run.config.device,
            }
            if run.config
            else None
        )

        runs_detail.append(
            RunDetailResponse(
                id=run.id,
                project_id=run.project_id,
                name=run.name,
                parent_run_id=run.parent_run_id,
                status=RunStatus(run.status),
                framework=Framework(run.framework),
                task=TaskType(run.task),
                created_by=run.created_by,
                created_at=run.created_at,
                started_at=run.started_at,
                finished_at=run.finished_at,
                duration_ms=run.duration_ms,
                terminal_error=run.terminal_error,
                terminal_error_code=run.terminal_error_code,
                config=config_dict,
                provenance=provenance_dict,
                metrics_summary=summary,
            )
        )

    # Compatibility check: runs must share the same task type to compare metrics meaningfully
    compatible = len(tasks_seen) == 1
    reason = None if compatible else f"Cannot compare runs with different tasks: {list(tasks_seen)}"

    # Metric comparisons table: {metric_key: {run_id: value}}
    metric_comparison: Dict[str, Dict[str, float]] = {}
    hyperparameter_deltas: Dict[str, Dict[str, Any]] = {}

    for rd in runs_detail:
        for m_key, m_val in rd.metrics_summary.items():
            if m_key not in metric_comparison:
                metric_comparison[m_key] = {}
            metric_comparison[m_key][rd.id] = m_val["value"]

        if rd.config and "hyperparameters" in rd.config:
            for hp_key, hp_val in rd.config["hyperparameters"].items():
                if hp_key not in hyperparameter_deltas:
                    hyperparameter_deltas[hp_key] = {}
                hyperparameter_deltas[hp_key][rd.id] = hp_val

    return ComparisonResponse(
        runs=runs_detail,
        compatible=compatible,
        incompatibility_reason=reason,
        metric_comparison=metric_comparison,
        hyperparameter_deltas=hyperparameter_deltas,
    )
