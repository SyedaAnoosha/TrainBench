"""Database schema and relational models."""
from datetime import datetime, timezone
from typing import List, Optional
import uuid
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.persistence.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProjectModel(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    runs: Mapped[List["RunModel"]] = relationship("RunModel", back_populates="project", cascade="all, delete-orphan")
    datasets: Mapped[List["DatasetModel"]] = relationship("DatasetModel", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_projects_owner_name"),
    )


class RunModel(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"run_{uuid.uuid4().hex[:12]}")
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    parent_run_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    framework: Mapped[str] = mapped_column(String(32), nullable=False)
    task: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    terminal_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    terminal_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    project: Mapped["ProjectModel"] = relationship("ProjectModel", back_populates="runs")
    parent_run: Mapped[Optional["RunModel"]] = relationship(
        "RunModel", remote_side=[id], back_populates="child_runs"
    )
    child_runs: Mapped[List["RunModel"]] = relationship("RunModel", back_populates="parent_run")
    config: Mapped[Optional["RunConfigModel"]] = relationship(
        "RunConfigModel", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    events: Mapped[List["RunEventModel"]] = relationship(
        "RunEventModel", back_populates="run", cascade="all, delete-orphan"
    )
    metrics: Mapped[List["MetricModel"]] = relationship(
        "MetricModel", back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[List["ArtifactModel"]] = relationship(
        "ArtifactModel", back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_runs_project_created", "project_id", "created_at"),
        Index("ix_runs_status_created", "status", "created_at"),
    )


class RunConfigModel(Base):
    __tablename__ = "run_configs"

    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), primary_key=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(64), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    device: Mapped[str] = mapped_column(String(32), nullable=False)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="config")
    dataset_ref: Mapped[Optional["DatasetModel"]] = relationship("DatasetModel", back_populates="run_configs")

    __table_args__ = (
        UniqueConstraint("run_id", "config_hash", name="uq_run_configs_run_hash"),
    )


class DatasetModel(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: f"ds_{uuid.uuid4().hex[:12]}")
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(256), nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(256), nullable=False)
    validation_status: Mapped[str] = mapped_column(String(32), default="validated", nullable=False)
    columns_json: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped["ProjectModel"] = relationship("ProjectModel", back_populates="datasets")
    run_configs: Mapped[List["RunConfigModel"]] = relationship("RunConfigModel", back_populates="dataset_ref")

    __table_args__ = (
        Index("ix_datasets_project_created", "project_id", "created_at"),
        UniqueConstraint("project_id", "checksum", name="uq_datasets_project_checksum"),
    )


class RunEventModel(Base):
    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="events")

    __table_args__ = (
        Index("ix_run_events_run_occurred", "run_id", "occurred_at"),
    )


class MetricModel(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    split: Mapped[str] = mapped_column(String(32), default="train", nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="metrics")

    __table_args__ = (
        UniqueConstraint("run_id", "name", "split", "step", name="uq_metrics_run_name_split_step"),
        Index("ix_metrics_run_name_step", "run_id", "name", "step"),
    )


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    run: Mapped["RunModel"] = relationship("RunModel", back_populates="artifacts")

    __table_args__ = (
        Index("ix_artifacts_run_kind", "run_id", "kind"),
        UniqueConstraint("checksum", "storage_key", name="uq_artifacts_checksum_key"),
    )


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_audit_resource_time", "resource", "timestamp"),
        Index("ix_audit_actor_time", "actor", "timestamp"),
    )
