"""Profile cache using MD5 file hashing to avoid redundant profiling."""

from __future__ import annotations

import hashlib
from typing import Any

from core.logging import get_logger

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.schemas import DataProfile

logger = get_logger(__name__)


class ProfileCache:
    """In-memory cache keyed by file content hash."""

    def __init__(self, max_entries: int = 100):
        self._cache: dict[str, DataProfile] = {}
        self._max_entries = max_entries

    def compute_hash(self, file_bytes: bytes) -> str:
        """Compute MD5 hash of file bytes."""
        return hashlib.md5(file_bytes).hexdigest()

    def get(self, file_hash: str) -> DataProfile | None:
        """Get cached profile by file hash."""
        profile = self._cache.get(file_hash)
        if profile:
            logger.info("cache_hit", file_hash=file_hash[:8])
        return profile

    def set(self, file_hash: str, profile: DataProfile) -> None:
        """Cache a profile. Evicts oldest if at capacity."""
        if len(self._cache) >= self._max_entries:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            logger.info("cache_evicted", evicted_hash=oldest_key[:8])

        self._cache[file_hash] = profile
        logger.info("cache_stored", file_hash=file_hash[:8])

    def clear(self) -> None:
        """Clear all cached profiles."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# Global cache instance
profile_cache = ProfileCache()
