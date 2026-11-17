"""Tests for domain configuration validation."""
import pytest
from backend.domain.models import (
    DatasetConfig,
    DeviceType,
    Framework,
    Hyperparameters,
    ModelConfig,
    OptimizerType,
    RunConfiguration,
    TaskType,
)
from backend.domain.validation import validate_run_configuration


def create_valid_config() -> RunConfiguration:
    return RunConfiguration(
        project_id="proj_1",
        name="Test Experiment",
        framework=Framework.PYTORCH,
        task=TaskType.CLASSIFICATION,
        dataset=DatasetConfig(
            name="synthetic_cls",
            task_type=TaskType.CLASSIFICATION,
            n_samples=500,
            n_features=10,
            n_classes=3,
            val_split=0.2,
        ),
        model=ModelConfig(
            architecture="mlp",
            hidden_dims=[32, 16],
            activation="relu",
        ),
        hyperparameters=Hyperparameters(
            epochs=5,
            batch_size=32,
            learning_rate=0.01,
            optimizer=OptimizerType.ADAM,
        ),
        seed=42,
        device=DeviceType.CPU,
    )


def test_valid_configuration_passes():
    config = create_valid_config()
    result = validate_run_configuration(config)
    assert result.is_valid
    assert len(result.errors) == 0


def test_invalid_task_dataset_mismatch():
    config = create_valid_config()
    config.dataset.task_type = TaskType.REGRESSION
    result = validate_run_configuration(config)
    assert not result.is_valid
    assert any("dataset.task_type" in e.field for e in result.errors)


def test_hyperparameter_boundaries():
    config = create_valid_config()
    config.hyperparameters.epochs = 0
    config.hyperparameters.learning_rate = 15.0
    result = validate_run_configuration(config)
    assert not result.is_valid
    assert any("epochs" in e.field for e in result.errors)
    assert any("learning_rate" in e.field for e in result.errors)


def test_batch_size_exceeding_training_samples():
    config = create_valid_config()
    config.dataset.n_samples = 50
    config.dataset.val_split = 0.2  # 40 train samples
    config.hyperparameters.batch_size = 100  # 100 > 40
    result = validate_run_configuration(config)
    assert not result.is_valid
    assert any("batch_size" in e.field for e in result.errors)


def test_unregistered_model_architecture():
    config = create_valid_config()
    config.model.architecture = "transformer_xl"
    result = validate_run_configuration(config)
    assert not result.is_valid
    assert any("model.architecture" in e.field for e in result.errors)
