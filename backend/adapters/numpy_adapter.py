"""NumPy Gradient Descent reference implementation from scratch."""
import json
import time
from typing import Any, Dict, List, Optional
import numpy as np
from backend.adapters.base import BaseTrainingAdapter, CancelChecker, MetricCallback, TrainingResult
from backend.adapters.synthetic_data import generate_dataset
from backend.artifacts.storage import storage_service
from backend.domain.models import ArtifactKind, MetricPoint, MetricSplit, RunConfiguration, TaskType


class NumPyTrainingAdapter(BaseTrainingAdapter):
    """
    Pure NumPy implementation of Gradient Descent for linear/logistic models and MLP.
    Provides verified numerical baseline for comparison against deep learning frameworks.
    """

    def train(
        self,
        config: RunConfiguration,
        on_metrics: Optional[MetricCallback] = None,
        is_cancelled: Optional[CancelChecker] = None,
        run_id: Optional[str] = None,
        dataset_storage_key: Optional[str] = None,
    ) -> TrainingResult:
        start_time = time.time()

        # Deterministic dataset generation / loading
        X_train, y_train, X_val, y_val = generate_dataset(
            config.dataset, seed=config.seed, dataset_storage_key=dataset_storage_key
        )

        n_train, n_features = X_train.shape
        epochs = config.hyperparameters.epochs
        batch_size = config.hyperparameters.batch_size
        lr = config.hyperparameters.learning_rate
        weight_decay = config.hyperparameters.weight_decay

        rng = np.random.RandomState(config.seed)

        artifacts: List[Dict[str, Any]] = []
        final_metrics: Dict[str, float] = {}
        all_metric_points: List[MetricPoint] = []
        total_steps = 0

        if config.task == TaskType.REGRESSION:
            # Linear model: y = X @ W + b
            W = rng.randn(n_features, 1).astype(np.float64) * 0.01
            b = np.zeros((1,), dtype=np.float64)
            y_train_2d = y_train.reshape(-1, 1).astype(np.float64)
            y_val_2d = y_val.reshape(-1, 1).astype(np.float64)
            X_train_64 = X_train.astype(np.float64)
            X_val_64 = X_val.astype(np.float64)

            for epoch in range(1, epochs + 1):
                if is_cancelled and is_cancelled():
                    break

                # Mini-batch shuffle
                indices = rng.permutation(n_train)
                epoch_loss = 0.0
                batches = int(np.ceil(n_train / batch_size))

                for batch_idx in range(batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(n_train, start_idx + batch_size)
                    batch_indices = indices[start_idx:end_idx]
                    X_b = X_train_64[batch_indices]
                    y_b = y_train_2d[batch_indices]
                    m = len(batch_indices)

                    # Forward pass
                    y_pred = np.dot(X_b, W) + b
                    diff = y_pred - y_b
                    loss = (0.5 / m) * np.sum(diff ** 2) + 0.5 * weight_decay * np.sum(W ** 2)

                    # Check numerical stability
                    if not np.isfinite(loss):
                        return TrainingResult(
                            success=False,
                            final_metrics={"error": -1.0},
                            total_steps=total_steps,
                            duration_ms=int((time.time() - start_time) * 1000),
                            artifacts=[],
                            error="Numerical instability: loss is NaN or Inf",
                        )

                    # Backward pass (gradients)
                    grad_W = (1.0 / m) * np.dot(X_b.T, diff) + weight_decay * W
                    grad_b = (1.0 / m) * np.sum(diff)

                    # Gradient update
                    W -= lr * grad_W
                    b -= lr * grad_b
                    epoch_loss += loss

                avg_train_loss = float(epoch_loss / batches)

                # Validation pass
                y_val_pred = np.dot(X_val_64, W) + b
                val_diff = y_val_pred - y_val_2d
                val_loss = float((0.5 / len(y_val)) * np.sum(val_diff ** 2))
                # MSE and R2 score
                val_mse = float(np.mean(val_diff ** 2))
                ss_tot = float(np.sum((y_val_2d - np.mean(y_val_2d)) ** 2))
                ss_res = float(np.sum(val_diff ** 2))
                r2_score = float(1.0 - (ss_res / (ss_tot + 1e-8)))

                total_steps += 1
                final_metrics = {
                    "train_loss": avg_train_loss,
                    "val_loss": val_loss,
                    "val_mse": val_mse,
                    "val_r2": r2_score,
                }

                metric_pts = [
                    MetricPoint(name="loss", split=MetricSplit.TRAIN, step=epoch, value=avg_train_loss),
                    MetricPoint(name="loss", split=MetricSplit.VAL, step=epoch, value=val_loss),
                    MetricPoint(name="r2_score", split=MetricSplit.VAL, step=epoch, value=r2_score),
                ]
                all_metric_points.extend(metric_pts)
                if on_metrics:
                    on_metrics(metric_pts)

            # Save checkpoint weights artifact
            weights_data = {
                "weights": W.tolist(),
                "bias": b.tolist(),
                "framework": "numpy",
                "task": "regression",
            }
            raw_bytes = json.dumps(weights_data).encode("utf-8")
            storage_prefix = f"runs/{run_id}" if run_id else f"runs/{config.name}"
            storage_key = f"{storage_prefix}/numpy_weights_step_{total_steps}.json"
            checksum, size_bytes = storage_service.save_bytes(storage_key, raw_bytes)
            artifacts.append({
                "kind": ArtifactKind.WEIGHTS,
                "filename": "numpy_weights.json",
                "checksum": checksum,
                "size_bytes": size_bytes,
                "storage_key": storage_key,
            })

        else:  # Classification (Multinomial Logistic Regression / Softmax)
            k = max(2, len(np.unique(y_train)), config.dataset.n_classes or 2)
            W = rng.randn(n_features, k).astype(np.float64) * 0.01
            b = np.zeros((k,), dtype=np.float64)
            X_train_64 = X_train.astype(np.float64)
            X_val_64 = X_val.astype(np.float64)

            for epoch in range(1, epochs + 1):
                if is_cancelled and is_cancelled():
                    break

                indices = rng.permutation(n_train)
                epoch_loss = 0.0
                batches = int(np.ceil(n_train / batch_size))
                correct_train = 0

                for batch_idx in range(batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min(n_train, start_idx + batch_size)
                    batch_indices = indices[start_idx:end_idx]
                    X_b = X_train_64[batch_indices]
                    y_b = y_train[batch_indices]
                    m = len(batch_indices)

                    # Softmax logits
                    logits = np.dot(X_b, W) + b
                    # Numerical stability shift
                    shift_logits = logits - np.max(logits, axis=1, keepdims=True)
                    exp_scores = np.exp(shift_logits)
                    probs = exp_scores / np.sum(exp_scores, axis=1, keepdims=True)

                    # Cross-entropy loss
                    core_log_probs = -np.log(np.maximum(probs[np.arange(m), y_b], 1e-15))
                    loss = np.mean(core_log_probs) + 0.5 * weight_decay * np.sum(W ** 2)

                    if not np.isfinite(loss):
                        return TrainingResult(
                            success=False,
                            final_metrics={"error": -1.0},
                            total_steps=total_steps,
                            duration_ms=int((time.time() - start_time) * 1000),
                            artifacts=[],
                            error="Numerical instability: softmax cross entropy loss is NaN",
                        )

                    # Gradients
                    dlogits = probs.copy()
                    dlogits[np.arange(m), y_b] -= 1.0
                    dlogits /= m

                    grad_W = np.dot(X_b.T, dlogits) + weight_decay * W
                    grad_b = np.sum(dlogits, axis=0)

                    W -= lr * grad_W
                    b -= lr * grad_b
                    epoch_loss += loss

                    preds = np.argmax(probs, axis=1)
                    correct_train += int(np.sum(preds == y_b))

                avg_train_loss = float(epoch_loss / batches)
                train_acc = float(correct_train / n_train)

                # Validation evaluation
                val_logits = np.dot(X_val_64, W) + b
                val_shift = val_logits - np.max(val_logits, axis=1, keepdims=True)
                val_exp = np.exp(val_shift)
                val_probs = val_exp / np.sum(val_exp, axis=1, keepdims=True)
                val_m = len(y_val)
                val_loss = float(np.mean(-np.log(np.maximum(val_probs[np.arange(val_m), y_val], 1e-15))))
                val_preds = np.argmax(val_probs, axis=1)
                val_acc = float(np.mean(val_preds == y_val))

                total_steps += 1
                final_metrics = {
                    "train_loss": avg_train_loss,
                    "val_loss": val_loss,
                    "train_accuracy": train_acc,
                    "val_accuracy": val_acc,
                }

                metric_pts = [
                    MetricPoint(name="loss", split=MetricSplit.TRAIN, step=epoch, value=avg_train_loss),
                    MetricPoint(name="loss", split=MetricSplit.VAL, step=epoch, value=val_loss),
                    MetricPoint(name="accuracy", split=MetricSplit.VAL, step=epoch, value=val_acc),
                ]
                all_metric_points.extend(metric_pts)
                if on_metrics:
                    on_metrics(metric_pts)

            # Checkpoint artifact
            weights_data = {
                "weights": W.tolist(),
                "bias": b.tolist(),
                "framework": "numpy",
                "task": "classification",
            }
            raw_bytes = json.dumps(weights_data).encode("utf-8")
            storage_prefix = f"runs/{run_id}" if run_id else f"runs/{config.name}"
            storage_key = f"{storage_prefix}/numpy_weights_step_{total_steps}.json"
            checksum, size_bytes = storage_service.save_bytes(storage_key, raw_bytes)
            artifacts.append({
                "kind": ArtifactKind.WEIGHTS,
                "filename": "numpy_weights.json",
                "checksum": checksum,
                "size_bytes": size_bytes,
                "storage_key": storage_key,
            })

        duration_ms = int((time.time() - start_time) * 1000)
        return TrainingResult(
            success=True,
            final_metrics=final_metrics,
            metric_points=all_metric_points,
            total_steps=total_steps,
            duration_ms=duration_ms,
            artifacts=artifacts,
        )
