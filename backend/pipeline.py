"""Fact Finder pipeline.

Phase 1: claim -> extract -> search (neutral + adversarial) -> fetch.
Phase 2: chunk/rank (BM25) -> LLM stance judge -> quote verify -> verdict in code.
`emit` is an optional callback(stage, message) used for the live UI trace.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import urlparse
from . import config
from .llm import generate_json
from .tinyfish import tf_search, tf_fetch
from .ranking import chunk_text, rank_chunks
from .judge import judge_page
from .verify import verify_quote
from .dates import extract_date
from .scoring import compute_verdict

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
    try:
        obj = generate_json(EXTRACT_SYSTEM, text, validate=_validate_extract)
        return obj["claims"][:config.MAX_CLAIMS]
    except Exception:
        # Fallback if LLM providers are rate limited or out of credits
        words = text.split()
        q = " ".join(words[:10])
        claim_type = "science" if any(w in text.lower() for w in ["study", "medical", "nasa", "earth", "moon", "science", "health", "water", "doctor", "research", "orbit", "planet"]) else "breaking_news"
        return [{
            "claim": text[:150].strip(),
            "claim_type": claim_type,
            "entities": [w.strip(".,!?") for w in words if w.istitle()][:3],
            "search_query": q
        }]


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


# ---------------------------------------------------------------- Phase 2
STANCE_VALUE = {"supports": 1, "contradicts": -1, "neutral": 0}
JUDGE_WORKERS = 3  # parallel LLM calls; low to respect free-tier rate limits


def _judge_one_page(claim_text: str, entities: list, page: dict, today: date):
    """Rank chunks, judge them, verify quotes. Returns (evidence_item|None, n_discarded, error|None)."""
    query = " ".join([claim_text, *entities])
    top = rank_chunks(query, chunk_text(page["text"]), k=2)
    if not top:
        return None, 0, None
    try:
        judgements = judge_page(claim_text, top)
    except Exception as e:
        return None, 0, f"{page['domain']}: {e}"

    verified, neutral, discarded = [], 0, 0
    for j in judgements:
        if j["stance"] == "neutral":
            neutral += 1
        elif verify_quote(j["quote"], page["text"]):
            verified.append(j)
        else:
            discarded += 1  # LLM quote not found in fetched text -> thrown away

    stances = {j["stance"] for j in verified}
    if len(stances) == 1:
        j = verified[0]
        stance, quote, reason = j["stance"], j["quote"], j["reason"]
    elif len(stances) > 1:  # same page says both things: do not take a side
        stance, quote, reason = "neutral", "", "Page contains mixed signals about the claim."
    elif neutral:
        stance, quote, reason = "neutral", "", judgements[0]["reason"]
    else:
        return None, discarded, None  # only unverified quotes: no usable evidence

    pub = extract_date(page["text"], today)
    return {
        "url": page["url"], "domain": page["domain"], "title": page.get("title"),
        "stance_label": stance, "stance": STANCE_VALUE[stance],
        "quote": quote, "reason": reason, "quote_verified": bool(quote),
        "date": pub,
    }, discarded, None


def judge_claim(claim: dict, sources: dict, emit=lambda s, m: None) -> dict:
    today = date.today()
    pages = [p for p in sources["pages"] if p["text"].strip()]
    emit("judge", f"Judging evidence from {len(pages)} pages")
    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as ex:
        results = list(ex.map(
            lambda p: _judge_one_page(claim["claim"], claim.get("entities", []), p, today), pages))

    items = [r[0] for r in results if r[0]]
    discarded = sum(r[1] for r in results)
    errors = [r[2] for r in results if r[2]]
    emit("verify", f"{sum(1 for i in items if i['quote_verified'])} quotes verified, "
                   f"{discarded} unverified quotes discarded")

    scored = compute_verdict(items, claim["claim_type"], today)
    emit("score", f"Verdict: {scored['verdict']} (confidence {scored['confidence']})")
    evidence = [{**e, "date": e["date"].isoformat() if e["date"] else None,
                 "date_known": e["date"] is not None} for e in scored["items"]]
    return {
        "verdict": scored["verdict"], "confidence": scored["confidence"],
        "score": scored["score"], "breakdown": scored["breakdown"],
        "evidence": evidence, "discarded_quotes": discarded,
        "pages_read": len(pages), "judge_errors": errors,
    }


def run_full(text: str, emit=lambda s, m: None) -> dict:
    """Complete pipeline: claim text in, verdicts with verified evidence out."""
    emit("extract", "Extracting claims")
    out = []
    for c in extract_claims(text):
        sources = gather_sources(c, emit)
        verdict = judge_claim(c, sources, emit)
        out.append({
            "claim": c["claim"], "claim_type": c["claim_type"],
            "entities": c.get("entities", []), "queries": sources["queries"],
            "fetch_errors": sources["fetch_errors"], **verdict,
        })
    return {"input": text, "claims": out}
