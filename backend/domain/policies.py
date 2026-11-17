"""Authorization and access control policies."""
from typing import Optional
from fastapi import HTTPException, status


class PolicyViolation(Exception):
    def __init__(self, message: str, code: str = "FORBIDDEN"):
        super().__init__(message)
        self.code = code
        self.message = message


def enforce_project_ownership(project_owner_id: str, current_user_id: Optional[str]) -> None:
    """Enforces that the current authenticated user owns the project."""
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if project_owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this project",
        )


def enforce_run_ownership(run_owner_id: str, current_user_id: Optional[str]) -> None:
    """Enforces that the current authenticated user owns the run."""
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if run_owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this run",
        )


def enforce_dataset_ownership(dataset_owner_id: str, current_user_id: Optional[str]) -> None:
    """Enforces that the current authenticated user owns the dataset."""
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    if dataset_owner_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You do not own this dataset",
        )
