"""Phase 1 pipeline: claim -> extract -> search (neutral + adversarial) -> fetch.

Later phases add: chunk/rank -> judge -> verify -> score (see SRS section 5).
`emit` is an optional callback(stage, message) used for the live UI trace.
"""
from urllib.parse import urlparse
from . import config
from .llm import generate_json
from .tinyfish import tf_search, tf_fetch

CLAIM_TYPES = {"breaking_news", "science", "other"}

EXTRACT_SYSTEM = """You extract checkable factual claims from text.
Return ONLY JSON: {"claims":[{"claim": str, "claim_type": "breaking_news"|"science"|"other",
"entities": [str], "search_query": str}]}
Rules: at most %d claims; each claim must be atomic, self-contained and factual
(skip opinions); search_query is a short neutral web query (max 12 words) that
would find sources about the claim. No commentary.""" % config.MAX_CLAIMS


def _validate_extract(obj: dict) -> None:
    claims = obj.get("claims")
    if not isinstance(claims, list):
        raise ValueError("'claims' must be a list")
    for c in claims:
        if not isinstance(c.get("claim"), str) or not c["claim"].strip():
            raise ValueError("claim text missing")
        if c.get("claim_type") not in CLAIM_TYPES:
            raise ValueError(f"bad claim_type: {c.get('claim_type')}")
        if not isinstance(c.get("search_query"), str) or not c["search_query"].strip():
            raise ValueError("search_query missing")
        c.setdefault("entities", [])


def extract_claims(text: str) -> list[dict]:
    text = text.strip()[:config.MAX_CLAIM_CHARS]
    obj = generate_json(EXTRACT_SYSTEM, text, validate=_validate_extract)
    return obj["claims"][:config.MAX_CLAIMS]


def build_queries(claim: dict) -> dict:
    """Neutral query from the LLM; adversarial variant built in code."""
    neutral = claim["search_query"].strip()
    adversarial = f"{neutral} fact check hoax false"
    return {"neutral": neutral, "adversarial": adversarial}


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def dedupe_by_domain(results: list[dict], limit: int) -> list[dict]:
    """Keep the first (highest-ranked) result per domain."""
    seen, out = set(), []
    for r in results:
        url = r.get("url")
        if not url:
            continue
        d = domain_of(url)
        if d and d not in seen:
            seen.add(d)
            out.append(r)
        if len(out) >= limit:
            break
    return out


def interleave(a: list, b: list) -> list:
    """Alternate neutral/adversarial results so both get top slots."""
    out = []
    for i in range(max(len(a), len(b))):
        if i < len(a):
            out.append(a[i])
        if i < len(b):
            out.append(b[i])
    return out


def gather_sources(claim: dict, emit=lambda stage, msg: None) -> dict:
    queries = build_queries(claim)
    emit("search", f"Searching: {queries['neutral']!r} + adversarial variant")
    found = {}
    for kind, q in queries.items():
        try:
            found[kind] = tf_search(q).get("results", [])
        except Exception as e:  # one failed search should not kill the run
            emit("search", f"{kind} search failed: {e}")
            found[kind] = []

    merged = interleave(found["neutral"], found["adversarial"])
    top = dedupe_by_domain(merged, config.MAX_PAGES)
    emit("fetch", f"Fetching {len(top)} pages from {len(top)} distinct domains")

    fetched = tf_fetch([r["url"] for r in top]) if top else {"results": [], "errors": []}
    meta = {r["url"]: r for r in top}
    pages = []
    for p in fetched.get("results", []):
        src = meta.get(p.get("url")) or meta.get(p.get("final_url")) or {}
        pages.append({
            "url": p.get("final_url") or p.get("url"),
            "domain": domain_of(p.get("final_url") or p.get("url") or ""),
            "title": p.get("title") or src.get("title"),
            "search_snippet": src.get("snippet"),
            "language": p.get("language"),
            "text": p.get("text") or "",
        })
    return {"queries": queries, "pages": pages, "fetch_errors": fetched.get("errors", [])}


def run_phase1(text: str, emit=lambda stage, msg: None) -> dict:
    emit("extract", "Extracting claims")
    claims = extract_claims(text)
    out = []
    for c in claims:
        out.append({**c, **gather_sources(c, emit)})
    return {"input": text, "claims": out}
