"""Provenance and fingerprint service for TrainBench experiments."""
import hashlib
import json
import platform
import sys
from typing import Any, Dict, Optional
from backend.domain.models import DatasetConfig, RunConfiguration


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_config_fingerprint(config: RunConfiguration) -> str:
    """Computes a deterministic SHA-256 hash of run configuration, excluding runtime metadata."""
    # Build clean canonical dictionary
    ds_source = config.dataset.source.value if hasattr(config.dataset.source, "value") else str(config.dataset.source)
    canonical = {
        "framework": config.framework.value,
        "task": config.task.value,
        "dataset": {
            "name": config.dataset.name,
            "task_type": config.dataset.task_type.value,
            "source": ds_source,
            "dataset_id": config.dataset.dataset_id,
            "target_column": config.dataset.target_column,
            "feature_columns": config.dataset.feature_columns,
            "n_samples": config.dataset.n_samples,
            "n_features": config.dataset.n_features,
            "n_classes": config.dataset.n_classes,
            "noise": config.dataset.noise,
            "val_split": config.dataset.val_split,
        },
        "model": {
            "architecture": config.model.architecture,
            "hidden_dims": config.model.hidden_dims,
            "activation": config.model.activation,
            "dropout": config.model.dropout,
        },
        "hyperparameters": {
            "epochs": config.hyperparameters.epochs,
            "batch_size": config.hyperparameters.batch_size,
            "learning_rate": config.hyperparameters.learning_rate,
            "optimizer": config.hyperparameters.optimizer.value,
            "weight_decay": config.hyperparameters.weight_decay,
            "momentum": config.hyperparameters.momentum,
        },
        "seed": config.seed,
        "device": config.device.value,
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return compute_sha256(encoded)


def compute_dataset_fingerprint(dataset_config: DatasetConfig, known_checksum: Optional[str] = None) -> str:
    """Computes a deterministic hash of dataset specification / content."""
    if known_checksum:
        return known_checksum
    ds_source = dataset_config.source.value if hasattr(dataset_config.source, "value") else str(dataset_config.source)
    canonical = {
        "name": dataset_config.name,
        "task_type": dataset_config.task_type.value,
        "source": ds_source,
        "dataset_id": dataset_config.dataset_id,
        "target_column": dataset_config.target_column,
        "feature_columns": dataset_config.feature_columns,
        "n_samples": dataset_config.n_samples,
        "n_features": dataset_config.n_features,
        "n_classes": dataset_config.n_classes,
        "noise": dataset_config.noise,
        "val_split": dataset_config.val_split,
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return compute_sha256(encoded)


def get_dependency_fingerprint() -> Dict[str, Any]:
    """Captures key environment dependencies and a composite hash."""
    import importlib.metadata

    packages: Dict[str, str] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }

    for pkg_name in ("numpy", "torch", "scipy"):
        try:
            packages[pkg_name] = importlib.metadata.version(pkg_name)
        except Exception:
            pass

    sorted_deps = json.dumps(packages, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "packages": packages,
        "hash": compute_sha256(sorted_deps),
    }


def generate_provenance_record(config: RunConfiguration, known_dataset_checksum: Optional[str] = None) -> Dict[str, Any]:
    """Generates complete provenance record for a run."""
    deps = get_dependency_fingerprint()
    return {
        "config_hash": compute_config_fingerprint(config),
        "dataset_hash": compute_dataset_fingerprint(config.dataset, known_checksum=known_dataset_checksum),
        "dependency_hash": deps["hash"],
        "dependencies": deps["packages"],
        "seed": config.seed,
        "device": config.device.value,
    }
