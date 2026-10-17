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


def tf_search(query: str) -> dict:
    """Live web search. Returns the raw JSON response."""
    r = requests.get(SEARCH_URL, params={"query": query},
                     headers=_headers(), timeout=20)
    if r.status_code != 200:
        raise TinyFishError(f"Search failed {r.status_code}: {r.text[:200]}")
    return r.json()


def tf_fetch(urls: list[str]) -> dict:
    """Fetch up to 10 URLs as markdown. Returns the raw JSON response."""
    if not urls:
        return {"results": [], "errors": []}
    if len(urls) > 10:
        raise ValueError("TinyFish Fetch accepts at most 10 URLs per request")
    r = requests.post(FETCH_URL, headers=_headers(),
                      json={"urls": urls, "format": "markdown"}, timeout=60)
    if r.status_code != 200:
        raise TinyFishError(f"Fetch failed {r.status_code}: {r.text[:200]}")
    return r.json()
