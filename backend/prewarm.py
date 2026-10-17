"""Run the demo claims once so they are cached:  python -m backend.prewarm
Re-run on demo morning (cache lasts CACHE_TTL_HOURS; set it to 72 for the finale)."""
import json
from pathlib import Path
from . import service


def main():
    claims = json.loads((Path(__file__).resolve().parent.parent / "demo" / "claims.json")
                        .read_text(encoding="utf-8"))
    for c in claims:
        print(f"-> {c['label']}: ", end="", flush=True)
        try:
            r = service.check(c["text"], lambda s, m: None)
            v = r["claims"][0]
            print(f"{v['verdict']} (confidence {v['confidence']}), expected: {c.get('expected', '?')}")
        except Exception as e:
            print(f"FAILED {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
