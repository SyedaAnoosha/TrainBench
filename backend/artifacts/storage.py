"""Artifact storage and checksum management."""
import hashlib
import os
from pathlib import Path
from typing import Optional, Tuple
from fastapi import HTTPException, status
from backend.config import settings


class StorageService:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.artifacts_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        """Resolves path and protects against directory traversal attacks."""
        resolved = (self.base_dir / storage_key).resolve()
        if not resolved.is_relative_to(self.base_dir.resolve()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid storage key: path traversal detected",
            )
        return resolved

    def save_bytes(self, storage_key: str, data: bytes) -> Tuple[str, int]:
        """Saves bytes to storage key and returns (sha256_checksum, size_bytes)."""
        target_path = self._resolve_safe_path(storage_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        target_path.write_bytes(data)
        checksum = hashlib.sha256(data).hexdigest()
        size_bytes = len(data)
        return checksum, size_bytes

    def read_bytes(self, storage_key: str) -> bytes:
        target_path = self._resolve_safe_path(storage_key)
        if not target_path.exists() or not target_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact file not found on disk",
            )
        return target_path.read_bytes()

    def get_file_path(self, storage_key: str) -> Path:
        target_path = self._resolve_safe_path(storage_key)
        if not target_path.exists() or not target_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact file not found on disk",
            )
        return target_path

    def exists(self, storage_key: str) -> bool:
        try:
            target_path = self._resolve_safe_path(storage_key)
            return target_path.exists() and target_path.is_file()
        except HTTPException:
            return False

    def delete_file(self, storage_key: str) -> bool:
        """Safely deletes an artifact file. Returns True if deleted, False if not found."""
        try:
            target_path = self._resolve_safe_path(storage_key)
            if target_path.exists() and target_path.is_file():
                target_path.unlink()
                return True
        except HTTPException:
            pass
        return False

    def cleanup_orphaned_quarantine(self) -> int:
        """Cleans up leftover files in the quarantine directory."""
        quarantine_dir = self.base_dir / "quarantine"
        if not quarantine_dir.exists():
            return 0
        deleted = 0
        for item in quarantine_dir.iterdir():
            if item.is_file():
                try:
                    item.unlink()
                    deleted += 1
                except Exception:
                    pass
        return deleted


storage_service = StorageService()
