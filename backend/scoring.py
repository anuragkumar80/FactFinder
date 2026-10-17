"""Verdict and confidence are computed HERE, in code, never by the LLM (SRS 5.3).

stance: +1 supports, -1 contradicts, 0 neutral
c: source credibility weight from sources.json
f: freshness weight exp(-age_days / half_life); 30d for breaking news, 365d otherwise
S = sum(stance*c*f) / sum(c*f)
S >= 0.35 Supported | S <= -0.35 Contradicted | otherwise Unclear
< 2 distinct domains with (non-neutral, verified) evidence => forced Unclear
confidence = |S| * coverage * agreement
"""
import json
import math
from datetime import date
from pathlib import Path

SUPPORT_T = 0.35
UNKNOWN_FRESHNESS = 0.5   # neutral weight for pages with no detectable date
MIN_DOMAINS = 2
FULL_COVERAGE_DOMAINS = 3
HALF_LIFE_DAYS = {"breaking_news": 30, "science": 365, "other": 365}

_SOURCES_PATH = Path(__file__).with_name("sources.json")
_cache = {}


def load_sources(path=None) -> dict:
    p = Path(path) if path else _SOURCES_PATH
    if p not in _cache:
        _cache[p] = json.loads(p.read_text(encoding="utf-8"))
    return _cache[p]


def _matches(domain: str, entry: str) -> bool:
    return domain == entry or domain.endswith("." + entry)


def credibility(domain: str, sources: dict | None = None) -> tuple[float, str]:
    """Return (weight, tier_name) for a domain."""
    sources = sources or load_sources()
    domain = (domain or "").lower()
    for tier in sources["tiers"]:
        if any(domain.endswith(s) for s in tier.get("suffixes", [])) or \
           any(_matches(domain, d) for d in tier.get("domains", [])):
            return tier["weight"], tier["name"]
    d = sources["default"]
    return d["weight"], d["name"]


def freshness_weight(pub_date: date | None, claim_type: str, today: date | None = None) -> float:
    if pub_date is None:
        return UNKNOWN_FRESHNESS
    today = today or date.today()
    age = max(0, (today - pub_date).days)
    return math.exp(-age / HALF_LIFE_DAYS.get(claim_type, 365))


def compute_verdict(items: list[dict], claim_type: str, today: date | None = None,
                    sources: dict | None = None) -> dict:
    """items: [{domain, stance (-1/0/1), date (date|None), ...}]

    Returns verdict, confidence, score and a breakdown for the UI tooltip.
    Each returned item is enriched with credibility, tier, freshness, weight.
    """
    enriched = []
    for it in items:
        c, tier = credibility(it["domain"], sources)
        f = freshness_weight(it.get("date"), claim_type, today)
        enriched.append({**it, "credibility": c, "tier": tier,
                         "freshness": round(f, 4), "weight": round(c * f, 4)})

    denom = sum(e["weight"] for e in enriched)
    evidence_domains = {e["domain"] for e in enriched if e["stance"] != 0}
    score = (sum(e["stance"] * e["weight"] for e in enriched) / denom) if denom else 0.0

    nonneutral_w = sum(e["weight"] for e in enriched if e["stance"] != 0)
    sign = 1 if score > 0 else -1 if score < 0 else 0
    agree_w = sum(e["weight"] for e in enriched if sign and e["stance"] == sign)
    agreement = (agree_w / nonneutral_w) if nonneutral_w else 0.0
    coverage = min(1.0, len(evidence_domains) / FULL_COVERAGE_DOMAINS)

    forced = len(evidence_domains) < MIN_DOMAINS
    if forced or abs(score) < SUPPORT_T:
        verdict = "Unclear"
    else:
        verdict = "Supported" if score > 0 else "Contradicted"
    confidence = 0.0 if forced else round(abs(score) * coverage * agreement, 3)

    return {
        "verdict": verdict,
        "confidence": confidence,
        "score": round(score, 4),
        "breakdown": {
            "evidence_domains": len(evidence_domains),
            "coverage": round(coverage, 3),
            "agreement": round(agreement, 3),
            "forced_unclear": forced,
            "thresholds": {"supported_at_or_above": SUPPORT_T,
                           "contradicted_at_or_below": -SUPPORT_T},
        },
        "items": enriched,
    }
