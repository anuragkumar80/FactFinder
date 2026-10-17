"""Offline tests: LLM and TinyFish are mocked, so no keys or network needed."""
import pytest
from backend import pipeline
from backend.llm import parse_json


def test_parse_json_strips_fences():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_validate_rejects_bad_claim_type():
    with pytest.raises(ValueError):
        pipeline._validate_extract({"claims": [
            {"claim": "x", "claim_type": "weird", "search_query": "q"}]})


def test_dedupe_by_domain_keeps_first_per_domain():
    res = [{"url": "https://www.bbc.com/a"}, {"url": "https://bbc.com/b"},
           {"url": "https://reuters.com/c"}]
    out = pipeline.dedupe_by_domain(res, 5)
    assert [r["url"] for r in out] == ["https://www.bbc.com/a", "https://reuters.com/c"]


def test_interleave_alternates():
    assert pipeline.interleave([1, 2], ["a", "b", "c"]) == [1, "a", 2, "b", "c"]


def test_run_phase1_with_mocks(monkeypatch):
    monkeypatch.setattr(pipeline, "generate_json", lambda *a, **k: {"claims": [
        {"claim": "Water boils at 100C at sea level", "claim_type": "science",
         "entities": [], "search_query": "water boiling point sea level"}]})
    monkeypatch.setattr(pipeline, "tf_search", lambda q: {"results": [
        {"url": "https://a.org/x", "title": "A"}, {"url": "https://b.org/y", "title": "B"}]})
    monkeypatch.setattr(pipeline, "tf_fetch", lambda urls: {
        "results": [{"url": u, "final_url": u, "text": "hello", "language": "en"} for u in urls],
        "errors": []})
    out = pipeline.run_phase1("Water boils at 100C at sea level")
    pages = out["claims"][0]["pages"]
    assert len(pages) == 2 and pages[0]["text"] == "hello"
    assert "fact check" in out["claims"][0]["queries"]["adversarial"]
