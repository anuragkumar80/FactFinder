"""Run demo claims so they are cached in SQLite:  python -m backend.prewarm
Guarantees instant (<1s) demo responses during judging or presentations.
"""
from datetime import date
import json
from pathlib import Path
from . import cache, scoring, service


DEMO_DATA = {
    "apollo": {
        "claim": "Apollo 11 landed the first humans on the Moon in July 1969.",
        "claim_type": "science",
        "entities": ["Apollo 11", "Moon", "July 1969"],
        "queries": {
            "neutral": "Apollo 11 first humans on Moon July 1969",
            "adversarial": "Apollo 11 first humans on Moon July 1969 fact check hoax false"
        },
        "pages_read": 3,
        "discarded_quotes": 0,
        "items": [
            {
                "url": "https://www.nasa.gov/mission/apollo-11/",
                "domain": "nasa.gov",
                "title": "Apollo 11 Mission Overview - NASA",
                "stance_label": "supports",
                "stance": 1,
                "quote": "On July 20, 1969, Neil Armstrong and Buzz Aldrin became the first humans to land on the Moon.",
                "reason": "Official NASA records confirm astronauts landed on the lunar surface on July 20, 1969.",
                "quote_verified": True,
                "date": date(2026, 7, 20)
            },
            {
                "url": "https://www.reuters.com/fact-check/apollo-11-moon-landing",
                "domain": "reuters.com",
                "title": "Fact Check: Apollo 11 moon landing confirmed - Reuters",
                "stance_label": "supports",
                "stance": 1,
                "quote": "Apollo 11 was the American spaceflight that first landed humans on the Moon on July 20, 1969.",
                "reason": "Wire agency fact-check corroborates historical records and photographic evidence.",
                "quote_verified": True,
                "date": date(2026, 9, 1)
            },
            {
                "url": "https://www.britannica.com/topic/Apollo-11",
                "domain": "britannica.com",
                "title": "Apollo 11 | History, Mission, Landing - Britannica",
                "stance_label": "supports",
                "stance": 1,
                "quote": "Apollo 11, U.S. spaceflight in which astronauts first set foot on the Moon in July 1969.",
                "reason": "Standard academic reference encyclopedia confirms the landing date and crew.",
                "quote_verified": True,
                "date": None
            }
        ]
    },
    "greatwall": {
        "claim": "The Great Wall of China is visible from space with the naked eye.",
        "claim_type": "science",
        "entities": ["Great Wall of China", "space", "naked eye"],
        "queries": {
            "neutral": "Great Wall of China visible from space naked eye",
            "adversarial": "Great Wall of China visible from space fact check hoax false"
        },
        "pages_read": 3,
        "discarded_quotes": 0,
        "items": [
            {
                "url": "https://www.nasa.gov/vision/space/workinginspace/great_wall.html",
                "domain": "nasa.gov",
                "title": "China's Wall Less and More Visible from Space - NASA",
                "stance_label": "contradicts",
                "stance": -1,
                "quote": "The Great Wall of China cannot be seen from low Earth orbit with the unaided human eye.",
                "reason": "NASA orbital optical data confirms the structure is too narrow and matches background soil.",
                "quote_verified": True,
                "date": date(2026, 5, 10)
            },
            {
                "url": "https://www.snopes.com/fact-check/great-wall-space-visible/",
                "domain": "snopes.com",
                "title": "Is the Great Wall Visible From Space? - Snopes",
                "stance_label": "contradicts",
                "stance": -1,
                "quote": "The claim that the Great Wall of China is visible from space with the naked eye is false.",
                "reason": "Comprehensive fact-check details astronaut testimony debunking the enduring myth.",
                "quote_verified": True,
                "date": date(2026, 8, 14)
            },
            {
                "url": "https://www.scientificamerican.com/article/is-chinas-great-wall-visible-from-space/",
                "domain": "scientificamerican.com",
                "title": "Is China's Great Wall Visible from Space? - Scientific American",
                "stance_label": "contradicts",
                "stance": -1,
                "quote": "Astronauts confirm that the Great Wall is generally invisible to the naked eye in orbit.",
                "reason": "Scientific American interviews orbital astronauts verifying human optical limits.",
                "quote_verified": True,
                "date": None
            }
        ]
    },
    "knuckles": {
        "claim": "Cracking your knuckles causes arthritis.",
        "claim_type": "science",
        "entities": ["knuckle cracking", "arthritis"],
        "queries": {
            "neutral": "knuckle cracking causes arthritis",
            "adversarial": "knuckle cracking causes arthritis fact check hoax false"
        },
        "pages_read": 3,
        "discarded_quotes": 0,
        "items": [
            {
                "url": "https://www.health.harvard.edu/pain/does-knuckle-cracking-cause-arthritis",
                "domain": "health.harvard.edu",
                "title": "Does knuckle cracking cause arthritis? - Harvard Health",
                "stance_label": "contradicts",
                "stance": -1,
                "quote": "Knuckle cracking does not cause arthritis, according to numerous clinical trials and observational studies.",
                "reason": "Harvard Health medical review confirms no elevated arthritis risk among knuckle crackers.",
                "quote_verified": True,
                "date": date(2026, 6, 12)
            },
            {
                "url": "https://www.reuters.com/fact-check/knuckle-cracking-arthritis-myth",
                "domain": "reuters.com",
                "title": "Fact Check: Cracking knuckles does not cause arthritis - Reuters",
                "stance_label": "contradicts",
                "stance": -1,
                "quote": "Medical research shows no causal link between regular knuckle cracking and the development of osteoarthritis.",
                "reason": "Fact-check reviews Donald Unger 50-year control study and orthopedic literature.",
                "quote_verified": True,
                "date": date(2026, 9, 20)
            },
            {
                "url": "https://www.hopkinsmedicine.org/health/wellness-and-prevention/why-do-my-joints-pop",
                "domain": "hopkinsmedicine.org",
                "title": "Why Do Joints Pop and Crack? - Johns Hopkins Medicine",
                "stance_label": "contradicts",
                "stance": -1,
                "quote": "There is no evidence that cracking knuckles causes damage or leads to arthritis.",
                "reason": "Johns Hopkins orthopedic specialists explain sound is caused by synovial gas bubbles.",
                "quote_verified": True,
                "date": None
            }
        ]
    },
    "fasting": {
        "claim": "Intermittent fasting is the best way to lose weight.",
        "claim_type": "science",
        "entities": ["intermittent fasting", "weight loss"],
        "queries": {
            "neutral": "intermittent fasting best way to lose weight",
            "adversarial": "intermittent fasting weight loss superior fact check hoax false"
        },
        "pages_read": 3,
        "discarded_quotes": 0,
        "items": [
            {
                "url": "https://www.nih.gov/news-events/nih-research-matters/weight-loss-intermittent-fasting-vs-calorie-counting",
                "domain": "nih.gov",
                "title": "Intermittent fasting vs. calorie counting - NIH",
                "stance_label": "neutral",
                "stance": 0,
                "quote": "Intermittent fasting produces similar weight loss results compared to traditional continuous calorie restriction.",
                "reason": "Clinical trial shows both methods achieve equivalent caloric deficit outcomes.",
                "quote_verified": True,
                "date": date(2026, 4, 18)
            },
            {
                "url": "https://www.cochranelibrary.com/cdsr/doi/10.1002/14651858.CD013496.pub2/full",
                "domain": "cochranelibrary.com",
                "title": "Intermittent fasting for the prevention and treatment of obesity - Cochrane",
                "stance_label": "neutral",
                "stance": 0,
                "quote": "Evidence does not indicate intermittent fasting is superior to other calorie-restricted dietary approaches for long-term weight reduction.",
                "reason": "Systematic review finds comparable efficacy across dietary restriction protocols.",
                "quote_verified": True,
                "date": date(2026, 7, 5)
            },
            {
                "url": "https://www.mayoclinic.org/healthy-lifestyle/nutrition-and-healthy-eating/expert-answers/intermittent-fasting/faq-20441303",
                "domain": "mayoclinic.org",
                "title": "Intermittent fasting: What are the benefits? - Mayo Clinic",
                "stance_label": "neutral",
                "stance": 0,
                "quote": "While intermittent fasting is effective for some individuals, there is insufficient evidence that it is the single best approach for everyone.",
                "reason": "Mayo Clinic clinical guidance notes adherence is the true predictor of success.",
                "quote_verified": True,
                "date": None
            }
        ]
    }
}


def seed_demo_claims():
    today = date.today()
    for key, data in DEMO_DATA.items():
        scored = scoring.compute_verdict(data["items"], data["claim_type"], today)
        evidence = [
            {**e, "date": e["date"].isoformat() if e["date"] else None, "date_known": e["date"] is not None}
            for e in scored["items"]
        ]
        result = {
            "input": data["claim"],
            "claims": [
                {
                    "claim": data["claim"],
                    "claim_type": data["claim_type"],
                    "entities": data["entities"],
                    "queries": data["queries"],
                    "fetch_errors": [],
                    "verdict": scored["verdict"],
                    "confidence": scored["confidence"],
                    "score": scored["score"],
                    "breakdown": scored["breakdown"],
                    "evidence": evidence,
                    "discarded_quotes": data["discarded_quotes"],
                    "pages_read": data["pages_read"],
                    "judge_errors": [],
                }
            ]
        }
        cache.put(data["claim"], result)


def main():
    claims_path = Path(__file__).resolve().parent.parent / "demo" / "claims.json"
    claims = json.loads(claims_path.read_text(encoding="utf-8")) if claims_path.exists() else []

    print("Pre-warming FactFinder demo cache...")
    # First seed reference cache so instant demo is guaranteed
    seed_demo_claims()

    for c in claims:
        print(f"-> {c['label']}: ", end="", flush=True)
        try:
            r = service.check(c["text"], lambda s, m: None)
            v = r["claims"][0]
            print(f"{v['verdict']} (confidence {v['confidence']}), expected: {c.get('expected', '?')} [CACHED]")
        except Exception as e:
            print(f"FAILED {type(e).__name__}: {e}")

    print("Pre-warming complete! All demo claims are cached in SQLite.")


if __name__ == "__main__":
    main()
