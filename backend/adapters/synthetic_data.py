"""Deterministic synthetic dataset generator for reproducible benchmarks."""
from typing import Tuple
import numpy as np
from backend.domain.models import DatasetConfig, TaskType


"""Deterministic synthetic and uploaded dataset loaders for reproducible benchmarks."""
import csv
import io
import json
from typing import Optional, Tuple
import numpy as np
from backend.artifacts.storage import storage_service
from backend.domain.models import DatasetConfig, TaskType


def load_dataset_from_storage(
    storage_key: str,
    config: DatasetConfig,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Loads a CSV or JSON dataset from artifact storage and returns (X_train, y_train, X_val, y_val)."""
    raw_bytes = storage_service.read_bytes(storage_key)
    lower = storage_key.lower()

    if lower.endswith(".json"):
        records = json.loads(raw_bytes.decode("utf-8"))
        if not records or not isinstance(records, list):
            raise ValueError("Uploaded JSON dataset must contain a list of records")
        target_col = config.target_column or list(records[0].keys())[-1]
        all_cols = list(records[0].keys())
        feature_cols = config.feature_columns or [c for c in all_cols if c != target_col]

        X_data = []
        y_data = []
        for r in records:
            X_data.append([float(r[col]) for col in feature_cols])
            y_data.append(r[target_col])
    else:
        text = raw_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        first_row = next(reader, None)
        if not first_row:
            raise ValueError("Uploaded CSV dataset is empty")
        all_cols = list(first_row.keys())
        target_col = config.target_column or all_cols[-1]
        feature_cols = config.feature_columns or [c for c in all_cols if c != target_col]

        X_data = []
        y_data = []
        for r in [first_row] + list(reader):
            if not r or not any(r.values()):
                continue
            X_data.append([float(r[col]) for col in feature_cols])
            y_data.append(r[target_col])

    X = np.array(X_data, dtype=np.float32)

    if config.task_type == TaskType.CLASSIFICATION:
        # Map distinct labels deterministically to 0..k-1
        unique_labels = sorted(list(set(str(v) for v in y_data)))
        label_map = {lbl: idx for idx, lbl in enumerate(unique_labels)}
        y = np.array([label_map[str(v)] for v in y_data], dtype=np.int64)
    else:
        y = np.array([float(v) for v in y_data], dtype=np.float32)

    # Deterministic train/validation split
    rng = np.random.RandomState(seed)
    n = len(X)
    perm = rng.permutation(n)
    X = X[perm]
    y = y[perm]

    val_count = max(1, int(n * config.val_split))
    train_count = n - val_count

    return X[:train_count], y[:train_count], X[train_count:], y[train_count:]


def generate_dataset(
    config: DatasetConfig,
    seed: int = 42,
    dataset_storage_key: Optional[str] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generates deterministic train and validation splits: (X_train, y_train, X_val, y_val).
    If dataset_storage_key is provided, loads the dataset from storage;
    otherwise generates a synthetic dataset.
    """
    if dataset_storage_key:
        return load_dataset_from_storage(dataset_storage_key, config, seed=seed)

    rng = np.random.RandomState(seed)
    n = config.n_samples
    d = config.n_features

    if config.task_type == TaskType.CLASSIFICATION:
        k = config.n_classes or 2
        samples_per_class = n // k
        X_list = []
        y_list = []
        for c in range(k):
            # Centroid in d-dimensional space
            centroid = rng.randn(d) * 2.0 + (c * 2.5)
            # Covariance noise
            noise_scale = config.noise if config.noise is not None else 0.2
            cluster = rng.randn(samples_per_class, d) * (1.0 + noise_scale) + centroid
            X_list.append(cluster)
            y_list.append(np.full(samples_per_class, c, dtype=np.int64))

        X = np.vstack(X_list).astype(np.float32)
        y = np.concatenate(y_list).astype(np.int64)

        # Shuffle deterministically
        perm = rng.permutation(len(y))
        X = X[perm]
        y = y[perm]

    else:  # Regression
        # True weight vector and bias
        w = rng.randn(d, 1).astype(np.float32)
        b = 1.5
        X = rng.randn(n, d).astype(np.float32)
        noise = rng.randn(n, 1).astype(np.float32) * (config.noise if config.noise is not None else 0.1)
        y = (np.dot(X, w) + b + noise).squeeze().astype(np.float32)

    # Train / Val Split
    val_count = max(1, int(n * config.val_split))
    train_count = n - val_count

    X_train, X_val = X[:train_count], X[train_count:]
    y_train, y_val = y[:train_count], y[train_count:]

    return X_train, y_train, X_val, y_val
