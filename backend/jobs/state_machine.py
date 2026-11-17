"""State machine rules and transition validation."""
from typing import Set
from backend.domain.models import RunStatus


class InvalidStateTransitionError(Exception):
    def __init__(self, from_state: RunStatus, to_state: RunStatus):
        super().__init__(f"Cannot transition run from {from_state.value} to {to_state.value}")
        self.from_state = from_state
        self.to_state = to_state


ALLOWED_TRANSITIONS = {
    RunStatus.QUEUED: {RunStatus.RUNNING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.RUNNING: {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED},
    RunStatus.SUCCEEDED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}


def validate_transition(current: RunStatus, target: RunStatus) -> None:
    allowed: Set[RunStatus] = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidStateTransitionError(current, target)
