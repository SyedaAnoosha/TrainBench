"""Domain validation rules and error representation."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from backend.domain.models import DatasetSource, Framework, RunConfiguration, TaskType


class ValidationErrorDetail(BaseModel):
    field: str
    message: str
    rejected_value: Optional[Any] = None


class ValidationResult:
    def __init__(self) -> None:
        self.errors: List[ValidationErrorDetail] = []

    def add_error(self, field: str, message: str, rejected_value: Optional[Any] = None) -> None:
        self.errors.append(ValidationErrorDetail(field=field, message=message, rejected_value=rejected_value))

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.is_valid,
            "error_count": len(self.errors),
            "errors": [err.model_dump() for err in self.errors],
        }


# Registered and allowed Framework + Task combinations
ALLOWED_COMBINATIONS = {
    (Framework.PYTORCH, TaskType.CLASSIFICATION): ["mlp", "linear"],
    (Framework.PYTORCH, TaskType.REGRESSION): ["mlp", "linear"],
    (Framework.NUMPY, TaskType.REGRESSION): ["linear", "mlp"],
    (Framework.NUMPY, TaskType.CLASSIFICATION): ["linear", "logistic"],
}


def validate_run_configuration(config: RunConfiguration) -> ValidationResult:
    """Validates run configuration against domain constraints, boundaries, and registered adapters."""
    result = ValidationResult()

    # 1. Project and Name
    if not config.project_id or not config.project_id.strip():
        result.add_error("project_id", "project_id must not be empty", config.project_id)
    if not config.name or not config.name.strip():
        result.add_error("name", "name must not be empty", config.name)
    elif any(sep in config.name for sep in ("/", "\\")) or config.name.strip() in (".", ".."):
        # Run names are used to build artifact storage paths — reject traversal segments.
        result.add_error(
            "name",
            "name must not contain path separators ('/', '\\') or be '.'/'..'",
            config.name,
        )

    # 2. Framework and Task compatibility
    combo = (config.framework, config.task)
    if combo not in ALLOWED_COMBINATIONS:
        result.add_error(
            "framework",
            f"Framework '{config.framework.value}' does not support task '{config.task.value}'",
            config.framework.value,
        )
    else:
        allowed_archs = ALLOWED_COMBINATIONS[combo]
        if config.model.architecture not in allowed_archs:
            result.add_error(
                "model.architecture",
                f"Architecture '{config.model.architecture}' is not registered for {config.framework.value}/{config.task.value}. Allowed: {allowed_archs}",
                config.model.architecture,
            )

    # 3. Dataset boundaries
    ds = config.dataset
    if ds.task_type != config.task:
        result.add_error(
            "dataset.task_type",
            f"Dataset task type '{ds.task_type.value}' must match run task type '{config.task.value}'",
            ds.task_type.value,
        )

    is_uploaded = (getattr(ds, "source", None) == DatasetSource.UPLOADED) or bool(ds.dataset_id)
    if is_uploaded:
        if not ds.dataset_id or not ds.dataset_id.strip():
            result.add_error("dataset.dataset_id", "dataset_id must be provided for uploaded datasets", ds.dataset_id)
        if not ds.target_column or not ds.target_column.strip():
            result.add_error("dataset.target_column", "target_column must be specified for uploaded datasets", ds.target_column)
    else:
        if ds.n_samples < 10 or ds.n_samples > 100000:
            result.add_error("dataset.n_samples", "n_samples must be between 10 and 100,000", ds.n_samples)

        if ds.n_features < 1 or ds.n_features > 500:
            result.add_error("dataset.n_features", "n_features must be between 1 and 500", ds.n_features)

        if ds.n_samples * ds.n_features > 5_000_000:
            result.add_error(
                "dataset",
                "n_samples * n_features must not exceed 5,000,000 to bound memory usage",
                ds.n_samples * ds.n_features,
            )

        if config.task == TaskType.CLASSIFICATION:
            if ds.n_classes is None or ds.n_classes < 2 or ds.n_classes > 100:
                result.add_error("dataset.n_classes", "n_classes for classification must be between 2 and 100", ds.n_classes)

    if ds.val_split <= 0.0 or ds.val_split >= 0.5:
        result.add_error("dataset.val_split", "val_split must be between 0.01 and 0.49", ds.val_split)

    # 4. Hyperparameter boundaries
    hp = config.hyperparameters
    if hp.epochs < 1 or hp.epochs > 1000:
        result.add_error("hyperparameters.epochs", "epochs must be between 1 and 1000", hp.epochs)

    if hp.batch_size < 1 or hp.batch_size > 4096:
        result.add_error("hyperparameters.batch_size", "batch_size must be between 1 and 4096", hp.batch_size)

    # Calculate effective training set size
    train_samples = int(ds.n_samples * (1.0 - ds.val_split))
    if hp.batch_size > train_samples:
        result.add_error(
            "hyperparameters.batch_size",
            f"batch_size ({hp.batch_size}) cannot exceed training set size ({train_samples})",
            hp.batch_size,
        )

    if hp.learning_rate < 1e-6 or hp.learning_rate > 10.0:
        result.add_error("hyperparameters.learning_rate", "learning_rate must be between 1e-6 and 10.0", hp.learning_rate)

    if hp.weight_decay < 0.0 or hp.weight_decay > 1.0:
        result.add_error("hyperparameters.weight_decay", "weight_decay must be between 0.0 and 1.0", hp.weight_decay)

    # 5. Model boundaries
    if config.model.architecture != "linear":
        if not config.model.hidden_dims or any(d < 1 or d > 2048 for d in config.model.hidden_dims):
            result.add_error("model.hidden_dims", "hidden_dims must be non-empty with values between 1 and 2048", config.model.hidden_dims)
        elif len(config.model.hidden_dims) > 16:
            result.add_error("model.hidden_dims", "hidden_dims cannot have more than 16 layers", len(config.model.hidden_dims))

    return result
