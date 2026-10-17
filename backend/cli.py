"""Phase 1 smoke test:  python -m backend.cli "your claim here"  [--save out.json]"""
import json
import sys
from .pipeline import run_phase1


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--save" in sys.argv:  # the path after --save is not the claim
        args = [a for a in args if a != sys.argv[sys.argv.index("--save") + 1]]
    if not args:
        sys.exit('usage: python -m backend.cli "claim text" [--save out.json]')
    result = run_phase1(args[0], emit=lambda s, m: print(f"[{s}] {m}", file=sys.stderr))
    preview = json.loads(json.dumps(result))
    for c in preview["claims"]:
        for p in c["pages"]:
            p["text"] = p["text"][:300] + f"... ({len(p['text'])} chars total)"
    print(json.dumps(preview, indent=2, ensure_ascii=False))
    if "--save" in sys.argv:
        path = sys.argv[sys.argv.index("--save") + 1]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"saved full output to {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
