import math
from datetime import date
from backend.scoring import compute_verdict, credibility, freshness_weight

TODAY = date(2026, 10, 17)


def item(domain, stance, d=None):
    return {"domain": domain, "stance": stance, "date": d}


def test_credibility_tiers():
    assert credibility("nasa.gov")[0] == 1.0
    assert credibility("www.who.int".replace("www.", ""))[0] == 1.0
    assert credibility("reuters.com")[0] == 0.9
    assert credibility("news.bbc.com")[0] == 0.7      # subdomain of listed domain
    assert credibility("en.wikipedia.org")[0] == 0.4
    assert credibility("reddit.com")[0] == 0.2
    assert credibility("random-blog.example")[1] == "unknown"
    assert credibility("evil-gov.com")[0] == 0.2      # look-alike must not match .gov


def test_freshness_decay_and_unknown():
    assert freshness_weight(TODAY, "breaking_news", TODAY) == 1.0
    assert math.isclose(freshness_weight(date(2026, 9, 17), "breaking_news", TODAY), math.exp(-30 / 30), rel_tol=1e-6)
    assert freshness_weight(date(2026, 9, 17), "science", TODAY) > 0.9
    assert freshness_weight(None, "science", TODAY) == 0.5
    assert freshness_weight(date(2030, 1, 1), "science", TODAY) == 1.0  # never negative age


def test_supported():
    r = compute_verdict([item("nasa.gov", 1, TODAY), item("reuters.com", 1, TODAY)], "science", TODAY)
    assert r["verdict"] == "Supported" and r["confidence"] > 0.5


def test_contradicted():
    r = compute_verdict([item("snopes.com", -1, TODAY), item("bbc.com", -1, TODAY),
                         item("reddit.com", 1, TODAY)], "other", TODAY)
    assert r["verdict"] == "Contradicted"


def test_single_domain_forces_unclear():
    r = compute_verdict([item("nasa.gov", 1, TODAY), item("nasa.gov", 1, TODAY)], "science", TODAY)
    assert r["verdict"] == "Unclear" and r["breakdown"]["forced_unclear"] and r["confidence"] == 0


def test_mixed_evidence_unclear():
    r = compute_verdict([item("reuters.com", 1, TODAY), item("bbc.com", -1, TODAY)], "other", TODAY)
    assert r["verdict"] == "Unclear"


def test_neutral_pages_dilute_score():
    strong = compute_verdict([item("nasa.gov", 1, TODAY), item("reuters.com", 1, TODAY)], "science", TODAY)
    diluted = compute_verdict([item("nasa.gov", 1, TODAY), item("reuters.com", 1, TODAY),
                               item("bbc.com", 0, TODAY), item("cnn.com", 0, TODAY),
                               item("npr.org", 0, TODAY)], "science", TODAY)
    assert diluted["score"] < strong["score"]


def test_old_source_loses_to_fresh_in_breaking_news():
    old = date(2025, 10, 17)
    r = compute_verdict([item("reuters.com", 1, old), item("bbc.com", 1, old),
                         item("apnews.com", -1, TODAY), item("nytimes.com", -1, TODAY)],
                        "breaking_news", TODAY)
    assert r["verdict"] == "Contradicted"


def test_empty_items():
    r = compute_verdict([], "other", TODAY)
    assert r["verdict"] == "Unclear" and r["confidence"] == 0
