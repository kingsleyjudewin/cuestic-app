"""
High-Performance In-Memory Cache for Research Management System.
Provides sub-millisecond retrieval (<1ms) for all research entities with
fine-grained invalidation upon any database mutation.
"""

import time
import threading
from typing import Any, Optional, Dict, List, Set


class ResearchCache:
    """Thread-safe TTL in-memory cache with tagged invalidation."""

    def __init__(self, default_ttl: float = 300.0):
        self._lock = threading.RLock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = default_ttl
        # Reverse index: tag -> set of keys
        self._tags: Dict[str, Set[str]] = {}

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if time.time() > entry["expires_at"]:
                self._remove_key_unlocked(key)
                return None
            return entry["data"]

    def set(self, key: str, data: Any, ttl: Optional[float] = None, tags: Optional[List[str]] = None) -> None:
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.time() + effective_ttl
        with self._lock:
            self._cache[key] = {
                "data": data,
                "expires_at": expires_at,
                "tags": tags or [],
            }
            if tags:
                for tag in tags:
                    if tag not in self._tags:
                        self._tags[tag] = set()
                    self._tags[tag].add(key)

    def delete(self, key: str) -> None:
        with self._lock:
            self._remove_key_unlocked(key)

    def invalidate_tag(self, tag: str) -> int:
        with self._lock:
            keys = self._tags.pop(tag, set())
            for key in keys:
                self._cache.pop(key, None)
            return len(keys)

    def invalidate_faculty(self, faculty_id: int) -> None:
        with self._lock:
            self.invalidate_tag(f"faculty:{faculty_id}")
            self.invalidate_tag("global:directory")
            self.invalidate_tag("global:teams")

    def invalidate_student(self, student_id: int) -> None:
        with self._lock:
            self.invalidate_tag(f"student:{student_id}")
            self.invalidate_tag("global:directory")

    def invalidate_project(self, project_id: int) -> None:
        with self._lock:
            self.invalidate_tag(f"project:{project_id}")
            self.invalidate_tag("global:projects")

    def invalidate_task(self, task_id: int) -> None:
        with self._lock:
            self.invalidate_tag(f"task:{task_id}")
            self.invalidate_tag("global:tasks")

    def _remove_key_unlocked(self, key: str) -> None:
        entry = self._cache.pop(key, None)
        if entry and "tags" in entry:
            for tag in entry["tags"]:
                if tag in self._tags:
                    self._tags[tag].discard(key)
                    if not self._tags[tag]:
                        self._tags.pop(tag, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._tags.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)


# Global singleton cache instance
research_cache = ResearchCache(default_ttl=300.0)
