"""Fact Finder CLI.

  python -m backend.cli "claim text"            full pipeline: verdict + evidence
  python -m backend.cli "claim text" --raw      Phase 1 only: search + fetched text
  add  --save out.json  to write the full JSON to a file
"""
import json
import sys
from .pipeline import run_full, run_phase1


def _log(stage, msg):
    print(f"[{stage}] {msg}", file=sys.stderr)


def main():
    argv = sys.argv[1:]
    save = None
    if "--save" in argv:
        i = argv.index("--save")
        save = argv[i + 1]
        del argv[i:i + 2]
    raw = "--raw" in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)

    result = run_phase1(args[0], _log) if raw else run_full(args[0], _log)

    if save:
        with open(save, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"saved full output to {save}", file=sys.stderr)

    if raw:  # truncate page text for a readable terminal preview
        for c in result["claims"]:
            for p in c["pages"]:
                p["text"] = p["text"][:300] + f"... ({len(p['text'])} chars total)"
    else:
        for c in result["claims"]:
            print(f"\n=== {c['verdict'].upper()} (confidence {c['confidence']}) :: {c['claim']}",
                  file=sys.stderr)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
