"""Adapter registry mapping framework to implementation."""
from typing import Dict, Type
from backend.adapters.base import BaseTrainingAdapter
from backend.adapters.numpy_adapter import NumPyTrainingAdapter
from backend.adapters.pytorch_adapter import PyTorchTrainingAdapter
from backend.domain.models import Framework

ADAPTER_REGISTRY: Dict[Framework, Type[BaseTrainingAdapter]] = {
    Framework.PYTORCH: PyTorchTrainingAdapter,
    Framework.NUMPY: NumPyTrainingAdapter,
}


def get_adapter(framework: Framework) -> BaseTrainingAdapter:
    adapter_cls = ADAPTER_REGISTRY.get(framework)
    if not adapter_cls:
        raise ValueError(f"No adapter registered for framework '{framework.value}'")
    return adapter_cls()
