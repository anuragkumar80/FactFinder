"""Orchestration around the pipeline: validation, cache, quota, fallback.

Order of decisions for one check:
  1. fresh cache hit            -> return it, labelled cached
  2. quota used up              -> last cached result (labelled) or QuotaExceeded
  3. per-IP rate limit          -> RateLimited
  4. live pipeline              -> cache and return
  5. live pipeline failed/empty -> last cached result (labelled) or CheckFailed
"""
import re
import time
from datetime import datetime, timezone

from . import cache, config
from .errors import CheckFailed, InputError, QuotaExceeded
from .pipeline import run_full


def clean_input(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", (text or "")).strip()
    if not text:
        raise InputError("Please paste a claim to check.")
    if len(text) > config.MAX_CLAIM_CHARS:
        raise InputError(f"Please keep the text under {config.MAX_CLAIM_CHARS} characters "
                         f"(yours is {len(text)}).")
    return text


def _usable(result: dict) -> bool:
    claims = result.get("claims") or []
    return bool(claims) and any(c.get("pages_read", 0) > 0 for c in claims)


def _with_meta(result: dict, **meta) -> dict:
    return {**result, "meta": meta}


def _from_cache(hit: dict, *, stale_fallback=False, reason=None) -> dict:
    return _with_meta(
        hit["result"], cached=True, stale_fallback=stale_fallback, fallback_reason=reason,
        cache_age_seconds=hit["age_seconds"],
        checked_at=datetime.fromtimestamp(hit["created_at"], timezone.utc).isoformat())


def check(text: str, emit=lambda s, m: None, rate_check=None) -> dict:
    text = clean_input(text)

    hit = cache.get_cached(text)
    if hit:
        emit("cache", "Cache hit: showing a result checked earlier (verified against live pages then)")
        return _from_cache(hit)

    if cache.fetch_quota_exhausted():
        stale = cache.get_any(text)
        if stale:
            emit("fallback", "Daily TinyFish quota used up: showing the last cached result")
            return _from_cache(stale, stale_fallback=True, reason="daily quota reached")
        raise QuotaExceeded("The daily live-check budget is used up. Try a demo claim, "
                            "or come back tomorrow.")

    if rate_check:
        rate_check()

    t0 = time.time()
    cache.add_usage("live_checks", 1)
    try:
        result = run_full(text, emit)
        error = None
    except Exception as e:  # LLMError, TinyFishError, network errors...
        result, error = None, f"{type(e).__name__}: {str(e)[:160]}"

    if result is not None and _usable(result):
        cache.put(text, result)
        return _with_meta(result, cached=False, stale_fallback=False, fallback_reason=None,
                          cache_age_seconds=0, elapsed_seconds=round(time.time() - t0, 1),
                          checked_at=datetime.now(timezone.utc).isoformat())

    stale = cache.get_any(text)
    if stale:
        emit("fallback", "Live search failed: showing the last cached result")
        return _from_cache(stale, stale_fallback=True, reason=error or "no pages could be read")
    if result is not None:  # pipeline ran but found nothing to read (or no claim): report honestly
        return _with_meta(result, cached=False, stale_fallback=False, fallback_reason=None,
                          cache_age_seconds=0, elapsed_seconds=round(time.time() - t0, 1),
                          checked_at=datetime.now(timezone.utc).isoformat())
    raise CheckFailed(error or "The live pipeline failed.")
