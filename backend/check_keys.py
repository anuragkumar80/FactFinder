"""Quick key test:  python -m backend.check_keys"""
from .tinyfish import tf_search, tf_fetch
from .llm import generate_json


def main():
    print("TinyFish search...", end=" ")
    r = tf_search("test query")
    print("OK,", len(r.get("results", [])), "results")
    print("TinyFish fetch...", end=" ")
    r = tf_fetch(["https://example.com"])
    print("OK,", len(r.get("results", [])), "pages, errors:", r.get("errors"))
    print("LLM...", end=" ")
    r = generate_json("Return JSON.", 'Return {"ok": true}')
    print("OK,", r)


if __name__ == "__main__":
    main()
