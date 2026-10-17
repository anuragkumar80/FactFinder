import pytest
from backend import service, cache, config
from backend.errors import InputError, QuotaExceeded, CheckFailed, RateLimited
from backend.ratelimit import RateLimiter

GOOD = {"input": "x", "claims": [{"claim": "c", "claim_type": "other", "verdict": "Supported",
                                   "confidence": 0.8, "pages_read": 3, "evidence": []}]}
EMPTY = {"input": "x", "claims": [{"claim": "c", "claim_type": "other", "verdict": "Unclear",
                                    "confidence": 0, "pages_read": 0, "evidence": []}]}


def test_input_validation():
    with pytest.raises(InputError):
        service.clean_input("   ")
    with pytest.raises(InputError):
        service.clean_input("a" * 1501)
    assert service.clean_input("  hello\x00 world ") == "hello world"


def test_live_then_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(service, "run_full", lambda t, e: calls.append(t) or GOOD)
    first = service.check("claim a")
    second = service.check("Claim   A")
    assert first["meta"]["cached"] is False and second["meta"]["cached"] is True
    assert len(calls) == 1  # second request never touched the live pipeline


def test_unusable_result_not_cached(monkeypatch):
    monkeypatch.setattr(service, "run_full", lambda t, e: EMPTY)
    r = service.check("claim b")
    assert r["meta"]["cached"] is False and cache.get_any("claim b") is None


def test_failure_falls_back_to_stale_cache(monkeypatch):
    cache.put("claim c", GOOD)
    monkeypatch.setattr(config, "CACHE_TTL_HOURS", 0)  # force the cache to be "expired"
    def boom(t, e): raise RuntimeError("tinyfish down")
    monkeypatch.setattr(service, "run_full", boom)
    r = service.check("claim c")
    assert r["meta"]["stale_fallback"] is True and "tinyfish down" in r["meta"]["fallback_reason"]


def test_failure_without_cache_raises(monkeypatch):
    def boom(t, e): raise RuntimeError("down")
    monkeypatch.setattr(service, "run_full", boom)
    with pytest.raises(CheckFailed):
        service.check("claim d")


def test_quota_exhausted(monkeypatch):
    monkeypatch.setattr(config, "FETCH_DAILY_LIMIT", 5)
    monkeypatch.setattr(service, "run_full", lambda t, e: pytest.fail("must not run live"))
    with pytest.raises(QuotaExceeded):
        service.check("claim e")
    cache.put("claim e", GOOD)
    monkeypatch.setattr(config, "CACHE_TTL_HOURS", 0)
    assert service.check("claim e")["meta"]["fallback_reason"] == "daily quota reached"


def test_rate_limit_only_applies_to_live_runs(monkeypatch):
    monkeypatch.setattr(service, "run_full", lambda t, e: GOOD)
    lim = RateLimiter(1, 60)
    service.check("claim f", rate_check=lambda: lim.check("ip"))
    service.check("claim f", rate_check=lambda: lim.check("ip"))  # cached: not counted
    with pytest.raises(RateLimited):
        service.check("claim g", rate_check=lambda: lim.check("ip"))


def test_rate_limiter_window():
    lim = RateLimiter(2, 60)
    lim.check("a"); lim.check("a"); lim.check("b")
    with pytest.raises(RateLimited):
        lim.check("a")
