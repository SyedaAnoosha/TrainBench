"""Tests for fingerprinting and provenance service."""
from backend.domain.models import (
    DatasetConfig,
    DeviceType,
    Framework,
    Hyperparameters,
    ModelConfig,
    RunConfiguration,
    TaskType,
)
from backend.domain.provenance import (
    compute_config_fingerprint,
    compute_dataset_fingerprint,
    generate_provenance_record,
    get_dependency_fingerprint,
)


def create_sample_config() -> RunConfiguration:
    return RunConfiguration(
        project_id="proj_1",
        name="Repro Run",
        framework=Framework.NUMPY,
        task=TaskType.REGRESSION,
        dataset=DatasetConfig(
            name="synthetic_reg",
            task_type=TaskType.REGRESSION,
            n_samples=200,
            n_features=5,
        ),
        model=ModelConfig(
            architecture="linear",
            hidden_dims=[],
        ),
        hyperparameters=Hyperparameters(
            epochs=10,
            batch_size=16,
            learning_rate=0.05,
        ),
        seed=123,
        device=DeviceType.CPU,
    )


def test_deterministic_fingerprint():
    config1 = create_sample_config()
    config2 = create_sample_config()

    hash1 = compute_config_fingerprint(config1)
    hash2 = compute_config_fingerprint(config2)
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256


def test_fingerprint_changes_on_hyperparameter_mutation():
    config1 = create_sample_config()
    config2 = create_sample_config()
    config2.hyperparameters.learning_rate = 0.01

    hash1 = compute_config_fingerprint(config1)
    hash2 = compute_config_fingerprint(config2)
    assert hash1 != hash2


def test_provenance_record_generation():
    config = create_sample_config()
    record = generate_provenance_record(config)

    assert "config_hash" in record
    assert "dataset_hash" in record
    assert "dependency_hash" in record
    assert "dependencies" in record
    assert record["seed"] == 123
    assert "python" in record["dependencies"]
