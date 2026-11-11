"""
Smart caching strategy for FinMind dashboard & analytics (#127).
Provides cache-aside retrieval, tag-based & user-scoped invalidation,
TTL expiration, and hit/miss/invalidation telemetry.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any, Callable


class SmartDashboardCache:
    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self.default_ttl_seconds = default_ttl_seconds
        self._lock = threading.RLock()
        self._store: dict[str, dict[str, Any]] = {}
        self._tag_index: dict[str, set[str]] = {}
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "invalidations": 0,
        }

    @staticmethod
    def build_key(user_id: int | str, namespace: str, params: dict[str, Any] | None = None) -> str:
        serialized = json.dumps(params or {}, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return f"finmind:u:{user_id}:ns:{namespace}:{digest}"

    def get(self, key: str, now: float | None = None) -> Any | None:
        ts = time.time() if now is None else now
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._metrics["misses"] += 1
                return None
            if entry["expires_at"] <= ts:
                self._evict_key(key)
                self._metrics["misses"] += 1
                return None
            self._metrics["hits"] += 1
            return entry["value"]

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
        tags: list[str] | set[str] | None = None,
        now: float | None = None,
    ) -> None:
        ts = time.time() if now is None else now
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        tag_set = set(tags or [])
        with self._lock:
            self._store[key] = {
                "value": value,
                "expires_at": ts + ttl,
                "tags": tag_set,
            }
            for tag in tag_set:
                self._tag_index.setdefault(tag, set()).add(key)
            self._metrics["sets"] += 1

    def get_or_compute(
        self,
        user_id: int | str,
        namespace: str,
        compute_fn: Callable[[], Any],
        params: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
        tags: list[str] | None = None,
        now: float | None = None,
    ) -> tuple[Any, bool]:
        key = self.build_key(user_id, namespace, params)
        cached = self.get(key, now=now)
        if cached is not None:
            return cached, True
        computed = compute_fn()
        default_tags = [f"user:{user_id}", f"ns:{namespace}", f"user:{user_id}:{namespace}"]
        merged_tags = list(set(default_tags + (tags or [])))
        self.set(key, computed, ttl_seconds=ttl_seconds, tags=merged_tags, now=now)
        return computed, False

    def invalidate_by_tag(self, tag: str) -> int:
        with self._lock:
            keys = list(self._tag_index.pop(tag, set()))
            for k in keys:
                self._evict_key(k)
            self._metrics["invalidations"] += len(keys)
            return len(keys)

    def invalidate_user_Mutation(self, user_id: int | str, entity_type: str = "expenses") -> int:
        """
        Invalidates dashboard & analytics caches impacted by a user mutation
        (e.g. adding/updating/deleting an expense, income, or budget).
        """
        impacted_namespaces = {
            "expenses": ["dashboard", "analytics", "digest", "budgets", "savings"],
            "incomes": ["dashboard", "analytics", "digest", "savings"],
            "budgets": ["dashboard", "budgets"],
            "accounts": ["dashboard", "analytics", "accounts"],
        }.get(entity_type, ["dashboard", "analytics"])

        removed = 0
        for ns in impacted_namespaces:
            removed += self.invalidate_by_tag(f"user:{user_id}:{ns}")
        return removed

    def _evict_key(self, key: str) -> None:
        entry = self._store.pop(key, None)
        if entry:
            for tag in entry.get("tags", set()):
                if tag in self._tag_index:
                    self._tag_index[tag].discard(key)

    def metrics(self) -> dict[str, Any]:
        with self._lock:
            total = self._metrics["hits"] + self._metrics["misses"]
            hit_rate = round((self._metrics["hits"] / total) * 100.0, 2) if total > 0 else 0.0
            return {
                **self._metrics,
                "active_entries": len(self._store),
                "hit_rate_pct": hit_rate,
            }


dashboard_cache = SmartDashboardCache(default_ttl_seconds=300)
