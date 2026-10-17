import time
from backend import cache, config


def test_hash_ignores_case_and_whitespace():
    assert cache.claim_hash("  The Earth   is ROUND ") == cache.claim_hash("the earth is round")
    assert cache.claim_hash("a") != cache.claim_hash("b")


def test_put_get_roundtrip():
    cache.put("claim one", {"claims": [{"verdict": "Supported"}]})
    hit = cache.get_cached("CLAIM  one")
    assert hit["result"]["claims"][0]["verdict"] == "Supported"
    assert hit["age_seconds"] <= 2


def test_miss_returns_none():
    assert cache.get_cached("never seen") is None
    assert cache.get_any("never seen") is None


def test_ttl_expiry_but_stale_still_available(monkeypatch):
    cache.put("old claim", {"x": 1})
    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 25 * 3600)
    assert cache.get_cached("old claim") is None          # past 24h TTL
    assert cache.get_any("old claim")["result"] == {"x": 1}  # but usable as fallback


def test_usage_counter_and_quota_exhaustion(monkeypatch):
    monkeypatch.setattr(config, "FETCH_DAILY_LIMIT", 25)
    assert cache.get_quota()["fetches"] == 0 and not cache.fetch_quota_exhausted()
    cache.add_usage("fetches", 10)
    cache.add_usage("searches", 2)
    q = cache.get_quota()
    assert q["fetches"] == 10 and q["searches"] == 2 and q["fetch_remaining"] == 15
    cache.add_usage("fetches", 10)
    assert cache.fetch_quota_exhausted()  # 5 left < 10 needed for another full check


def test_bad_usage_kind_rejected():
    import pytest
    with pytest.raises(ValueError):
        cache.add_usage("drop table", 1)
