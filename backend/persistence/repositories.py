"""Database repositories providing clean data access for domain logic."""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.domain.models import ArtifactKind, MetricPoint, RunStatus
from backend.observability.logging import get_correlation_id
from backend.persistence.schema import (
    ArtifactModel,
    AuditEventModel,
    DatasetModel,
    MetricModel,
    ProjectModel,
    RunConfigModel,
    RunEventModel,
    RunModel,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, name: str, description: Optional[str], owner_id: str) -> ProjectModel:
        project = ProjectModel(name=name, description=description, owner_id=owner_id)
        self.session.add(project)
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def get_by_id(self, project_id: str) -> Optional[ProjectModel]:
        stmt = select(ProjectModel).where(ProjectModel.id == project_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_owner(self, owner_id: str, limit: int = 50, offset: int = 0) -> List[ProjectModel]:
        stmt = (
            select(ProjectModel)
            .where(ProjectModel.owner_id == owner_id)
            .order_by(desc(ProjectModel.updated_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class RunRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(
        self,
        run_id: str,
        project_id: str,
        name: str,
        framework: str,
        task: str,
        created_by: str,
        parent_run_id: Optional[str] = None,
        status: str = RunStatus.QUEUED.value,
    ) -> RunModel:
        run = RunModel(
            id=run_id,
            project_id=project_id,
            name=name,
            framework=framework,
            task=task,
            created_by=created_by,
            parent_run_id=parent_run_id,
            status=status,
        )
        self.session.add(run)
        await self.session.flush()
        return run

    async def save_config(
        self,
        run_id: str,
        config_json: str,
        seed: int,
        config_hash: str,
        dataset_hash: str,
        dependency_fingerprint: str,
        device: str,
        dataset_id: Optional[str] = None,
    ) -> RunConfigModel:
        cfg = RunConfigModel(
            run_id=run_id,
            dataset_id=dataset_id,
            config_json=config_json,
            seed=seed,
            config_hash=config_hash,
            dataset_hash=dataset_hash,
            dependency_fingerprint=dependency_fingerprint,
            device=device,
        )
        self.session.add(cfg)
        await self.session.flush()
        return cfg

    async def add_event(self, run_id: str, event_type: str, payload: Optional[Dict[str, Any]] = None) -> RunEventModel:
        payload_str = json.dumps(payload) if payload else None
        event = RunEventModel(run_id=run_id, event_type=event_type, payload=payload_str)
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_by_id(self, run_id: str, load_details: bool = True) -> Optional[RunModel]:
        stmt = select(RunModel).where(RunModel.id == run_id)
        if load_details:
            stmt = stmt.options(
                selectinload(RunModel.config),
                selectinload(RunModel.events),
                selectinload(RunModel.artifacts),
            )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_active(self) -> int:
        """Number of runs currently queued or running."""
        stmt = (
            select(func.count(RunModel.id))
            .where(RunModel.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]))
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def list_runs(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        framework: Optional[str] = None,
        task: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RunModel]:
        stmt = select(RunModel)
        if owner_id:
            stmt = stmt.where(RunModel.created_by == owner_id)
        if project_id:
            stmt = stmt.where(RunModel.project_id == project_id)
        if status:
            stmt = stmt.where(RunModel.status == status)
        if framework:
            stmt = stmt.where(RunModel.framework == framework)
        if task:
            stmt = stmt.where(RunModel.task == task)

        stmt = stmt.order_by(desc(RunModel.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def atomic_claim(self, run_id: str) -> bool:
        """Atomic compare-and-set to claim a queued run."""
        now = utcnow()
        stmt = (
            update(RunModel)
            .where(RunModel.id == run_id, RunModel.status == RunStatus.QUEUED.value)
            .values(status=RunStatus.RUNNING.value, started_at=now)
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        await self.session.commit()
        return result.rowcount > 0

    async def set_terminal_status(
        self,
        run_id: str,
        status: RunStatus,
        error: Optional[str] = None,
        error_code: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> bool:
        now = utcnow()
        stmt = (
            update(RunModel)
            .where(RunModel.id == run_id, RunModel.status.in_([RunStatus.QUEUED.value, RunStatus.RUNNING.value]))
            .values(
                status=status.value,
                finished_at=now,
                duration_ms=duration_ms,
                terminal_error=error,
                terminal_error_code=error_code,
            )
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        await self.session.commit()
        return result.rowcount > 0


class MetricRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def batch_insert(self, run_id: str, points: List[MetricPoint]) -> None:
        if not points:
            return
        now = utcnow()
        for p in points:
            split_val = p.split.value if hasattr(p.split, "value") else str(p.split)
            stmt = sqlite_insert(MetricModel).values(
                run_id=run_id,
                name=p.name,
                split=split_val,
                step=p.step,
                value=p.value,
                unit=p.unit,
                timestamp=now,
            ).on_conflict_do_update(
                index_elements=["run_id", "name", "split", "step"],
                set_={"value": p.value, "timestamp": now}
            )
            await self.session.execute(stmt)
        await self.session.flush()

    async def get_series(
        self,
        run_id: str,
        names: Optional[List[str]] = None,
        split: Optional[str] = None,
        max_points: int = 1000,
    ) -> List[MetricModel]:
        stmt = select(MetricModel).where(MetricModel.run_id == run_id)
        if names:
            stmt = stmt.where(MetricModel.name.in_(names))
        if split:
            stmt = stmt.where(MetricModel.split == split)
        stmt = stmt.order_by(MetricModel.step.asc()).limit(max_points)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_summary(self, run_id: str) -> Dict[str, Any]:
        """Returns latest metric values per name and split."""
        stmt = (
            select(MetricModel)
            .where(MetricModel.run_id == run_id)
            .order_by(MetricModel.step.desc())
        )
        result = await self.session.execute(stmt)
        metrics = result.scalars().all()
        summary: Dict[str, Any] = {}
        for m in metrics:
            key = f"{m.name}_{m.split}"
            if key not in summary:
                summary[key] = {
                    "name": m.name,
                    "split": m.split,
                    "value": m.value,
                    "step": m.step,
                    "unit": m.unit,
                }
        return summary


class ArtifactRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        run_id: str,
        kind: ArtifactKind,
        filename: str,
        checksum: str,
        size_bytes: int,
        storage_key: str,
    ) -> ArtifactModel:
        kind_str = kind.value if hasattr(kind, "value") else str(kind)
        # Check if an artifact with (checksum, storage_key) already exists to avoid unique constraint violations
        existing_stmt = select(ArtifactModel).where(
            ArtifactModel.checksum == checksum,
            ArtifactModel.storage_key == storage_key,
        )
        existing_res = await self.session.execute(existing_stmt)
        existing = existing_res.scalar_one_or_none()
        if existing:
            return existing

        artifact = ArtifactModel(
            run_id=run_id,
            kind=kind_str,
            filename=filename,
            checksum=checksum,
            size_bytes=size_bytes,
            storage_key=storage_key,
        )
        self.session.add(artifact)
        await self.session.flush()
        return artifact

    async def get_by_id(self, artifact_id: str) -> Optional[ArtifactModel]:
        stmt = select(ArtifactModel).where(ArtifactModel.id == artifact_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_run(self, run_id: str) -> List[ArtifactModel]:
        stmt = select(ArtifactModel).where(ArtifactModel.run_id == run_id).order_by(ArtifactModel.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class DatasetRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        dataset_id: str,
        project_id: str,
        owner_id: str,
        original_filename: str,
        format: str,
        size_bytes: int,
        checksum: str,
        storage_key: str,
        columns_json: str,
        row_count: int,
        validation_status: str = "validated",
    ) -> DatasetModel:
        dataset = DatasetModel(
            id=dataset_id,
            project_id=project_id,
            owner_id=owner_id,
            original_filename=original_filename,
            format=format,
            size_bytes=size_bytes,
            checksum=checksum,
            storage_key=storage_key,
            columns_json=columns_json,
            row_count=row_count,
            validation_status=validation_status,
        )
        self.session.add(dataset)
        await self.session.flush()
        return dataset

    async def get_by_id(self, dataset_id: str) -> Optional[DatasetModel]:
        stmt = select(DatasetModel).where(DatasetModel.id == dataset_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_project_and_checksum(self, project_id: str, checksum: str) -> Optional[DatasetModel]:
        stmt = select(DatasetModel).where(
            DatasetModel.project_id == project_id,
            DatasetModel.checksum == checksum,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(
        self,
        project_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DatasetModel]:
        stmt = (
            select(DatasetModel)
            .where(DatasetModel.project_id == project_id)
            .order_by(DatasetModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_references(self, dataset_id: str) -> int:
        stmt = select(func.count(RunConfigModel.run_id)).where(RunConfigModel.dataset_id == dataset_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def delete(self, dataset_id: str) -> bool:
        stmt = delete(DatasetModel).where(DatasetModel.id == dataset_id)
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        await self.session.flush()
        return result.rowcount > 0


class AuditEventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        actor: str,
        action: str,
        resource: str,
        outcome: str = "success",
        correlation_id: Optional[str] = None,
    ) -> AuditEventModel:
        cid = correlation_id or get_correlation_id() or "-"
        event = AuditEventModel(
            actor=actor,
            action=action,
            resource=resource,
            outcome=outcome,
            correlation_id=cid,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def list_by_resource(self, resource: str, limit: int = 50) -> List[AuditEventModel]:
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.resource == resource)
            .order_by(desc(AuditEventModel.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_actor(self, actor: str, limit: int = 50) -> List[AuditEventModel]:
        stmt = (
            select(AuditEventModel)
            .where(AuditEventModel.actor == actor)
            .order_by(desc(AuditEventModel.timestamp))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
