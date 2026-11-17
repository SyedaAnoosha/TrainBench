"""Domain entities and value objects."""
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional
from pydantic import BaseModel, Field, StringConstraints


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def is_terminal(self) -> bool:
        return self in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED)

    def can_transition_to(self, target: "RunStatus") -> bool:
        if self == RunStatus.QUEUED:
            return target in (RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED)
        if self == RunStatus.RUNNING:
            return target in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED)
        return False  # Terminal states cannot transition


class Framework(str, Enum):
    PYTORCH = "pytorch"
    NUMPY = "numpy"


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"


class DeviceType(str, Enum):
    CPU = "cpu"
    CUDA = "cuda"


class OptimizerType(str, Enum):
    ADAM = "adam"
    SGD = "sgd"
    RMSPROP = "rmsprop"


class MetricSplit(str, Enum):
    TRAIN = "train"
    VAL = "val"
    TEST = "test"


class ArtifactKind(str, Enum):
    CHECKPOINT = "checkpoint"
    WEIGHTS = "weights"
    SUMMARY = "summary"
    LOG = "log"


class MetricPoint(BaseModel):
    name: str
    split: MetricSplit = MetricSplit.TRAIN
    step: int
    value: float
    unit: Optional[str] = None


class Hyperparameters(BaseModel):
    epochs: int = Field(..., ge=1, le=1000)
    batch_size: int = Field(..., ge=1, le=4096)
    learning_rate: float = Field(..., ge=1e-6, le=10.0)
    optimizer: OptimizerType = OptimizerType.ADAM
    weight_decay: float = Field(default=0.0, ge=0.0, le=1.0)
    momentum: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class DatasetSource(str, Enum):
    SYNTHETIC = "synthetic"
    UPLOADED = "uploaded"


class DatasetConfig(BaseModel):
    name: str
    task_type: TaskType
    source: DatasetSource = DatasetSource.SYNTHETIC
    dataset_id: Optional[str] = None
    target_column: Optional[str] = None
    feature_columns: Optional[List[str]] = None
    n_samples: int = Field(default=1000, ge=10, le=100000)
    n_features: int = Field(default=10, ge=1, le=500)
    n_classes: Optional[int] = Field(default=2, ge=2, le=100)
    noise: Optional[float] = Field(default=0.1, ge=0.0, le=1.0)
    val_split: float = Field(default=0.2, gt=0.0, lt=0.5)


class ModelConfig(BaseModel):
    architecture: str = "mlp"  # mlp, linear
    hidden_dims: List[int] = Field(default_factory=lambda: [64, 32])
    activation: str = "relu"  # relu, tanh, sigmoid
    dropout: float = Field(default=0.0, ge=0.0, le=0.9)


class RunConfiguration(BaseModel):
    project_id: str
    name: str
    framework: Framework
    task: TaskType
    dataset: DatasetConfig
    model: ModelConfig
    hyperparameters: Hyperparameters
    seed: int = 42
    device: DeviceType = DeviceType.CPU
    tags: List[Annotated[str, StringConstraints(max_length=64)]] = Field(
        default_factory=list, max_length=32
    )
