"""Pydantic schemas for the TrainBench API contracts."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.domain.models import (
    ArtifactKind,
    DatasetConfig,
    DeviceType,
    Framework,
    Hyperparameters,
    MetricPoint,
    ModelConfig,
    RunStatus,
    TaskType,
)


class ProblemDetails(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: Optional[str] = None
    correlation_id: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=1000)


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    owner_id: str
    created_at: datetime
    updated_at: datetime
    run_count: int = 0


class RunCreateRequest(BaseModel):
    project_id: str
    name: str = Field(..., min_length=1, max_length=128)
    framework: Framework
    task: TaskType
    dataset: DatasetConfig
    model: ModelConfig
    hyperparameters: Hyperparameters
    seed: int = 42
    device: DeviceType = DeviceType.CPU
    tags: List[str] = Field(default_factory=list)


class RunSummaryResponse(BaseModel):
    id: str
    project_id: str
    name: str
    status: RunStatus
    framework: Framework
    task: TaskType
    created_at: datetime
    duration_ms: Optional[int] = None
    primary_metric: Optional[Dict[str, Any]] = None


class RunEventResponse(BaseModel):
    id: int
    event_type: str
    payload: Optional[Dict[str, Any]] = None
    occurred_at: datetime


class ArtifactResponse(BaseModel):
    id: str
    run_id: str
    kind: ArtifactKind
    filename: str
    checksum: str
    size_bytes: int
    download_url: str
    created_at: datetime


class RunDetailResponse(BaseModel):
    id: str
    project_id: str
    name: str
    parent_run_id: Optional[str] = None
    status: RunStatus
    framework: Framework
    task: TaskType
    created_by: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    terminal_error: Optional[str] = None
    terminal_error_code: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    provenance: Optional[Dict[str, Any]] = None
    events: List[RunEventResponse] = Field(default_factory=list)
    artifacts: List[ArtifactResponse] = Field(default_factory=list)
    metrics_summary: Dict[str, Any] = Field(default_factory=dict)


class MetricFilterResponse(BaseModel):
    run_id: str
    points: List[MetricPoint]


class ComparisonRequest(BaseModel):
    run_ids: List[str] = Field(..., min_length=2, max_length=10)


class ComparisonResponse(BaseModel):
    runs: List[RunDetailResponse]
    compatible: bool
    incompatibility_reason: Optional[str] = None
    metric_comparison: Dict[str, Dict[str, float]]
    hyperparameter_deltas: Dict[str, Dict[str, Any]]


class DatasetColumnInfo(BaseModel):
    name: str
    dtype: str
    unique_count: int = 0
    sample_values: List[Any] = Field(default_factory=list)


class DatasetResponse(BaseModel):
    id: str
    project_id: str
    owner_id: str
    original_filename: str
    format: str
    size_bytes: int
    checksum: str
    validation_status: str
    columns: List[str] = Field(default_factory=list)
    column_details: List[DatasetColumnInfo] = Field(default_factory=list)
    row_count: int
    created_at: datetime
