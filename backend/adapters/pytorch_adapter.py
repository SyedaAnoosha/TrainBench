"""PyTorch training adapter for classification and regression tasks."""
import io
import time
from typing import Any, Dict, List, Optional
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from backend.adapters.base import BaseTrainingAdapter, CancelChecker, MetricCallback, TrainingResult
from backend.adapters.synthetic_data import generate_dataset
from backend.artifacts.storage import storage_service
from backend.domain.models import ArtifactKind, MetricPoint, MetricSplit, OptimizerType, RunConfiguration, TaskType


class DynamicMLP(nn.Module):
    def __init__(self, in_features: int, hidden_dims: List[int], out_features: int, activation: str = "relu", dropout: float = 0.0):
        super().__init__()
        layers: List[nn.Module] = []
        act_cls = nn.Tanh if activation == "tanh" else (nn.Sigmoid if activation == "sigmoid" else nn.ReLU)

        curr_in = in_features
        for h in hidden_dims:
            layers.append(nn.Linear(curr_in, h))
            layers.append(act_cls())
            if dropout > 0.0:
                layers.append(nn.Dropout(dropout))
            curr_in = h

        layers.append(nn.Linear(curr_in, out_features))
        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)


class DynamicLinear(nn.Module):
    def __init__(self, in_features: int, out_features: int):
        super().__init__()
        self.linear = nn.Linear(in_features, out_features)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.linear(x)


class PyTorchTrainingAdapter(BaseTrainingAdapter):
    def train(
        self,
        config: RunConfiguration,
        on_metrics: Optional[MetricCallback] = None,
        is_cancelled: Optional[CancelChecker] = None,
        run_id: Optional[str] = None,
        dataset_storage_key: Optional[str] = None,
    ) -> TrainingResult:
        start_time = time.time()

        # Set seeds for complete determinism
        torch.manual_seed(config.seed)
        np.random.seed(config.seed)

        # Device selection with fallback
        device_str = "cuda" if config.device.value == "cuda" and torch.cuda.is_available() else "cpu"
        device = torch.device(device_str)

        # Generate / load data
        X_train_np, y_train_np, X_val_np, y_val_np = generate_dataset(
            config.dataset, seed=config.seed, dataset_storage_key=dataset_storage_key
        )

        n_features = X_train_np.shape[1]
        is_classification = config.task == TaskType.CLASSIFICATION

        if is_classification:
            out_features = max(2, len(np.unique(y_train_np)), config.dataset.n_classes or 2)
            y_train_tensor = torch.tensor(y_train_np, dtype=torch.long)
            y_val_tensor = torch.tensor(y_val_np, dtype=torch.long)
            criterion = nn.CrossEntropyLoss()
        else:
            out_features = 1
            y_train_tensor = torch.tensor(y_train_np, dtype=torch.float32).unsqueeze(1)
            y_val_tensor = torch.tensor(y_val_np, dtype=torch.float32).unsqueeze(1)
            criterion = nn.MSELoss()

        X_train_tensor = torch.tensor(X_train_np, dtype=torch.float32)
        X_val_tensor = torch.tensor(X_val_np, dtype=torch.float32)

        train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
        train_loader = DataLoader(
            train_dataset,
            batch_size=config.hyperparameters.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(config.seed),
        )

        # Build Model
        arch = config.model.architecture.lower()
        if arch == "linear":
            model = DynamicLinear(n_features, out_features)
        else:
            model = DynamicMLP(
                in_features=n_features,
                hidden_dims=config.model.hidden_dims,
                out_features=out_features,
                activation=config.model.activation,
                dropout=config.model.dropout,
            )

        model.to(device)

        # Optimizer
        hp = config.hyperparameters
        opt_type = hp.optimizer
        if opt_type == OptimizerType.SGD:
            optimizer = optim.SGD(
                model.parameters(),
                lr=hp.learning_rate,
                weight_decay=hp.weight_decay,
                momentum=hp.momentum if hp.momentum is not None else 0.0,
            )
        elif opt_type == OptimizerType.RMSPROP:
            optimizer = optim.RMSprop(
                model.parameters(),
                lr=hp.learning_rate,
                weight_decay=hp.weight_decay,
            )
        else:
            optimizer = optim.Adam(
                model.parameters(),
                lr=hp.learning_rate,
                weight_decay=hp.weight_decay,
            )

        epochs = hp.epochs
        artifacts: List[Dict[str, Any]] = []
        final_metrics: Dict[str, float] = {}
        all_metric_points: List[MetricPoint] = []
        total_steps = 0

        X_val_device = X_val_tensor.to(device)
        y_val_device = y_val_tensor.to(device)

        for epoch in range(1, epochs + 1):
            if is_cancelled and is_cancelled():
                break

            model.train()
            epoch_loss = 0.0
            batch_count = 0

            for bx, by in train_loader:
                bx, by = bx.to(device), by.to(device)
                optimizer.zero_grad()
                out = model(bx)
                loss = criterion(out, by)

                if torch.isnan(loss) or torch.isinf(loss):
                    return TrainingResult(
                        success=False,
                        final_metrics={"error": -1.0},
                        total_steps=total_steps,
                        duration_ms=int((time.time() - start_time) * 1000),
                        artifacts=[],
                        error="PyTorch training aborted: loss is NaN or Inf",
                    )

                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                batch_count += 1

            avg_train_loss = epoch_loss / max(1, batch_count)

            # Validation evaluation
            model.eval()
            with torch.no_grad():
                val_out = model(X_val_device)
                val_loss_t = criterion(val_out, y_val_device)
                val_loss = float(val_loss_t.item())

                metric_points = [
                    MetricPoint(name="loss", split=MetricSplit.TRAIN, step=epoch, value=float(avg_train_loss)),
                    MetricPoint(name="loss", split=MetricSplit.VAL, step=epoch, value=val_loss),
                ]

                if is_classification:
                    preds = torch.argmax(val_out, dim=1)
                    acc = float((preds == y_val_device).float().mean().item())
                    metric_points.append(
                        MetricPoint(name="accuracy", split=MetricSplit.VAL, step=epoch, value=acc)
                    )
                    final_metrics = {
                        "train_loss": avg_train_loss,
                        "val_loss": val_loss,
                        "val_accuracy": acc,
                    }
                else:
                    ss_tot = torch.sum((y_val_device - torch.mean(y_val_device)) ** 2)
                    ss_res = torch.sum((y_val_device - val_out) ** 2)
                    r2 = float(1.0 - (ss_res / (ss_tot + 1e-8)).item())
                    metric_points.append(
                        MetricPoint(name="r2_score", split=MetricSplit.VAL, step=epoch, value=r2)
                    )
                    final_metrics = {
                        "train_loss": avg_train_loss,
                        "val_loss": val_loss,
                        "val_r2": r2,
                    }

                total_steps += 1
                all_metric_points.extend(metric_points)
                if on_metrics:
                    on_metrics(metric_points)

        # Save model checkpoint
        buf = io.BytesIO()
        torch.save({
            "model_state_dict": model.state_dict(),
            "config": config.model_dump(),
            "final_metrics": final_metrics,
            "steps": total_steps,
        }, buf)
        raw_bytes = buf.getvalue()

        storage_prefix = f"runs/{run_id}" if run_id else f"runs/{config.name}"
        storage_key = f"{storage_prefix}/checkpoint_pytorch_step_{total_steps}.pt"
        checksum, size_bytes = storage_service.save_bytes(storage_key, raw_bytes)
        artifacts.append({
            "kind": ArtifactKind.CHECKPOINT,
            "filename": f"checkpoint_step_{total_steps}.pt",
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
