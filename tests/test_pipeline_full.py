"""End-to-end with mocked LLM + TinyFish: proves verification and scoring are wired together."""
from backend import pipeline, judge

GOOD = "NASA confirmed that the Apollo 11 crew landed on the Moon on July 20, 1969."
PAGE_TXT = "Published: October 1, 2026\n\n" + GOOD + " Tracking stations worldwide confirmed it."


def _setup(monkeypatch, judge_fn):
    monkeypatch.setattr(pipeline, "generate_json", lambda *a, **k: {"claims": [
        {"claim": "Apollo 11 landed on the Moon", "claim_type": "science",
         "entities": ["Apollo 11"], "search_query": "Apollo 11 moon landing"}]})
    monkeypatch.setattr(pipeline, "tf_search", lambda q: {"results": [
        {"url": "https://nasa.gov/a", "title": "A"}, {"url": "https://reuters.com/b", "title": "B"}]})
    monkeypatch.setattr(pipeline, "tf_fetch", lambda urls: {
        "results": [{"url": u, "final_url": u, "text": PAGE_TXT, "language": "en"} for u in urls],
        "errors": []})
    monkeypatch.setattr(pipeline, "judge_page", judge_fn)


def test_supported_when_quotes_verify(monkeypatch):
    _setup(monkeypatch, lambda claim, chunks: [
        {"chunk_id": chunks[0]["chunk_id"], "stance": "supports", "quote": GOOD, "reason": "States it."}])
    c = pipeline.run_full("Apollo 11 landed on the Moon")["claims"][0]
    assert c["verdict"] == "Supported" and c["discarded_quotes"] == 0
    assert all(e["quote_verified"] for e in c["evidence"])
    assert c["evidence"][0]["date"] == "2026-10-01"


def test_fabricated_quotes_are_discarded_and_verdict_unclear(monkeypatch):
    _setup(monkeypatch, lambda claim, chunks: [
        {"chunk_id": chunks[0]["chunk_id"], "stance": "contradicts",
         "quote": "NASA admitted the landing was staged in a film studio.", "reason": "Made up."}])
    c = pipeline.run_full("Apollo 11 landed on the Moon")["claims"][0]
    assert c["verdict"] == "Unclear" and c["discarded_quotes"] == 2 and c["evidence"] == []


def test_judge_failure_does_not_crash(monkeypatch):
    def boom(claim, chunks):
        raise RuntimeError("rate limited")
    _setup(monkeypatch, boom)
    c = pipeline.run_full("Apollo 11 landed on the Moon")["claims"][0]
    assert c["verdict"] == "Unclear" and len(c["judge_errors"]) == 2
