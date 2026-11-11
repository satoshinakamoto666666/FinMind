import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.smart_cache import SmartDashboardCache


def test_cache_aside_hit_and_miss():
    cache = SmartDashboardCache(default_ttl_seconds=60)
    calls = 0

    def compute():
        nonlocal calls
        calls += 1
        return {"total_spent": 420.50}

    val1, hit1 = cache.get_or_compute(42, "dashboard", compute, params={"month": "2026-11"}, now=1000.0)
    val2, hit2 = cache.get_or_compute(42, "dashboard", compute, params={"month": "2026-11"}, now=1010.0)

    assert hit1 is False
    assert hit2 is True
    assert calls == 1
    assert val1 == val2 == {"total_spent": 420.50}
    assert cache.metrics()["hit_rate_pct"] == 50.0


def test_ttl_expiration_triggers_recompute():
    cache = SmartDashboardCache(default_ttl_seconds=30)
    val1, hit1 = cache.get_or_compute(7, "analytics", lambda: {"v": 1}, now=100.0)
    val2, hit2 = cache.get_or_compute(7, "analytics", lambda: {"v": 2}, now=135.0)
    assert hit1 is False
    assert hit2 is False
    assert val1 == {"v": 1}
    assert val2 == {"v": 2}


def test_selective_mutation_invalidation_preserves_other_users():
    cache = SmartDashboardCache(default_ttl_seconds=300)
    cache.get_or_compute(1, "dashboard", lambda: {"u": 1}, now=10.0)
    cache.get_or_compute(1, "analytics", lambda: {"u": 1, "a": True}, now=10.0)
    cache.get_or_compute(2, "dashboard", lambda: {"u": 2}, now=10.0)

    evicted = cache.invalidate_user_Mutation(1, entity_type="expenses")
    assert evicted == 2

    _, u1_hit = cache.get_or_compute(1, "dashboard", lambda: {"u": 1, "fresh": True}, now=12.0)
    _, u2_hit = cache.get_or_compute(2, "dashboard", lambda: {"u": 2}, now=12.0)
    assert u1_hit is False
    assert u2_hit is True
