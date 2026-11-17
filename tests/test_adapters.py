"""Tests for NumPy and PyTorch training adapters."""
from backend.adapters.numpy_adapter import NumPyTrainingAdapter
from backend.adapters.pytorch_adapter import PyTorchTrainingAdapter
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


def test_numpy_regression_adapter():
    config = RunConfiguration(
        project_id="p1",
        name="numpy_reg_test",
        framework=Framework.NUMPY,
        task=TaskType.REGRESSION,
        dataset=DatasetConfig(
            name="synth_reg",
            task_type=TaskType.REGRESSION,
            n_samples=200,
            n_features=4,
            noise=0.05,
            val_split=0.2,
        ),
        model=ModelConfig(architecture="linear", hidden_dims=[]),
        hyperparameters=Hyperparameters(
            epochs=15,
            batch_size=32,
            learning_rate=0.05,
            optimizer=OptimizerType.SGD,
        ),
        seed=42,
        device=DeviceType.CPU,
    )

    adapter = NumPyTrainingAdapter()
    result = adapter.train(config)

    assert result.success
    assert result.total_steps == 15
    assert "val_loss" in result.final_metrics
    assert "val_r2" in result.final_metrics
    assert len(result.artifacts) > 0


def test_numpy_classification_adapter():
    config = RunConfiguration(
        project_id="p1",
        name="numpy_cls_test",
        framework=Framework.NUMPY,
        task=TaskType.CLASSIFICATION,
        dataset=DatasetConfig(
            name="synth_cls",
            task_type=TaskType.CLASSIFICATION,
            n_samples=200,
            n_features=4,
            n_classes=2,
            noise=0.1,
            val_split=0.2,
        ),
        model=ModelConfig(architecture="linear", hidden_dims=[]),
        hyperparameters=Hyperparameters(
            epochs=10,
            batch_size=32,
            learning_rate=0.05,
            optimizer=OptimizerType.SGD,
        ),
        seed=42,
        device=DeviceType.CPU,
    )

    adapter = NumPyTrainingAdapter()
    result = adapter.train(config)

    assert result.success
    assert "val_accuracy" in result.final_metrics
    assert result.final_metrics["val_accuracy"] >= 0.5


def test_pytorch_classification_adapter():
    config = RunConfiguration(
        project_id="p1",
        name="pytorch_cls_test",
        framework=Framework.PYTORCH,
        task=TaskType.CLASSIFICATION,
        dataset=DatasetConfig(
            name="synth_cls",
            task_type=TaskType.CLASSIFICATION,
            n_samples=200,
            n_features=6,
            n_classes=3,
            val_split=0.2,
        ),
        model=ModelConfig(
            architecture="mlp",
            hidden_dims=[16, 8],
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

    adapter = PyTorchTrainingAdapter()
    result = adapter.train(config)

    assert result.success
    assert result.total_steps == 5
    assert "val_accuracy" in result.final_metrics
    assert len(result.artifacts) == 1
    assert result.artifacts[0]["filename"].startswith("checkpoint_")


def test_pytorch_regression_adapter():
    config = RunConfiguration(
        project_id="p1",
        name="pytorch_reg_test",
        framework=Framework.PYTORCH,
        task=TaskType.REGRESSION,
        dataset=DatasetConfig(
            name="synth_reg",
            task_type=TaskType.REGRESSION,
            n_samples=200,
            n_features=5,
            noise=0.1,
            val_split=0.2,
        ),
        model=ModelConfig(
            architecture="mlp",
            hidden_dims=[16, 8],
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

    adapter = PyTorchTrainingAdapter()
    result = adapter.train(config)

    assert result.success
    assert result.total_steps == 5
    assert "val_loss" in result.final_metrics
    assert "val_r2" in result.final_metrics
    assert len(result.artifacts) == 1
    assert result.artifacts[0]["filename"].startswith("checkpoint_")
