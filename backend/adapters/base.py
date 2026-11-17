"""Abstract base adapter and execution contracts."""
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.domain.models import MetricPoint, RunConfiguration


class StepMetrics(BaseModel):
    epoch: int
    step: int
    train_loss: float
    val_loss: Optional[float] = None
    train_metric: Optional[float] = None
    val_metric: Optional[float] = None
    metric_name: Optional[str] = None


class TrainingResult(BaseModel):
    success: bool
    final_metrics: Dict[str, float]
    metric_points: List[MetricPoint] = Field(default_factory=list)
    total_steps: int
    duration_ms: int
    artifacts: List[Dict[str, Any]]
    error: Optional[str] = None


MetricCallback = Callable[[List[MetricPoint]], None]
CancelChecker = Callable[[], bool]


class BaseTrainingAdapter(ABC):
    @abstractmethod
    def train(
        self,
        config: RunConfiguration,
        on_metrics: Optional[MetricCallback] = None,
        is_cancelled: Optional[CancelChecker] = None,
        run_id: Optional[str] = None,
        dataset_storage_key: Optional[str] = None,
    ) -> TrainingResult:
        """Executes the training workflow deterministically given configuration."""
        pass
