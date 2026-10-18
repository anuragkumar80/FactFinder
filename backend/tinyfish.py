"""Thin wrappers around TinyFish Search and Fetch (REST, X-API-Key header).

Verified against docs.tinyfish.ai:
  Search: GET  https://api.search.tinyfish.ai?query=...
          -> {"query": str, "results": [{position, site_name, title, url, snippet?}]}
  Fetch:  POST https://api.fetch.tinyfish.ai  {"urls": [<=10], "format": "markdown"}
          -> {"results": [{url, final_url, language, text, format, title?}],
              "errors": [{url, error}]}   (per-URL failures come back with HTTP 200)
"""
import requests
from . import config

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"


class TinyFishError(RuntimeError):
    pass


def _headers():
    if not config.TINYFISH_API_KEY:
        raise TinyFishError("TINYFISH_API_KEY is not set")
    return {"X-API-Key": config.TINYFISH_API_KEY}


def _tavily_search(query: str) -> dict:
    r = requests.post(
        "https://api.tavily.com/search",
        json={"api_key": config.TAVILY_API_KEY, "query": query, "max_results": 5},
        timeout=20,
    )
    if r.status_code != 200:
        raise TinyFishError(f"Tavily search failed {r.status_code}: {r.text[:200]}")
    data = r.json()
    results = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
        })
    return {"query": query, "results": results}


def _tavily_fetch(urls: list[str]) -> dict:
    if not urls:
        return {"results": [], "errors": []}
    try:
        r = requests.post(
            "https://api.tavily.com/extract",
            json={"api_key": config.TAVILY_API_KEY, "urls": urls},
            timeout=60,
        )
        if r.status_code == 200:
            data = r.json()
            results = []
            for item in data.get("results", []):
                results.append({
                    "url": item.get("url"),
                    "final_url": item.get("url"),
                    "title": item.get("title", ""),
                    "text": item.get("raw_content") or item.get("content") or "",
                    "format": "markdown",
                    "language": "en",
                })
            errors = [{"url": f.get("url"), "error": f.get("error")} for f in data.get("failed_results", [])]
            return {"results": results, "errors": errors}
    except Exception:
        pass

    results, errors = [], []
    for u in urls:
        try:
            resp = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if resp.status_code == 200:
                results.append({"url": u, "final_url": str(resp.url), "text": resp.text[:50000], "format": "text", "language": "en"})
            else:
                errors.append({"url": u, "error": f"HTTP {resp.status_code}"})
        except Exception as err:
            errors.append({"url": u, "error": str(err)})
    return {"results": results, "errors": errors}


def tf_search(query: str) -> dict:
    """Live web search. Uses TinyFish if key configured, otherwise falls back to Tavily."""
    if config.TINYFISH_API_KEY:
        r = requests.get(SEARCH_URL, params={"query": query},
                         headers=_headers(), timeout=20)
        if r.status_code != 200:
            raise TinyFishError(f"Search failed {r.status_code}: {r.text[:200]}")
        return r.json()
    elif config.TAVILY_API_KEY:
        return _tavily_search(query)
    else:
        raise TinyFishError("Neither TINYFISH_API_KEY nor TAVILY_API_KEY is set")


def tf_fetch(urls: list[str]) -> dict:
    """Fetch up to 10 URLs. Uses TinyFish if key configured, otherwise falls back to Tavily."""
    if not urls:
        return {"results": [], "errors": []}
    if config.TINYFISH_API_KEY:
        if len(urls) > 10:
            raise ValueError("TinyFish Fetch accepts at most 10 URLs per request")
        r = requests.post(FETCH_URL, headers=_headers(),
                          json={"urls": urls, "format": "markdown"}, timeout=60)
        if r.status_code != 200:
            raise TinyFishError(f"Fetch failed {r.status_code}: {r.text[:200]}")
        return r.json()
    elif config.TAVILY_API_KEY:
        return _tavily_fetch(urls)
    else:
        raise TinyFishError("Neither TINYFISH_API_KEY nor TAVILY_API_KEY is set")
