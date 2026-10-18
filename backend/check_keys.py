"""Quick key test:  python -m backend.check_keys"""
from . import config
from .tinyfish import tf_search, tf_fetch
from .llm import generate_json


def main():
    print("=== FactFinder API Key Verification ===")

    # 1. Search & Fetch Check
    if config.TINYFISH_API_KEY:
        print("TinyFish search...", end=" ")
        try:
            r = tf_search("test query")
            print("OK,", len(r.get("results", [])), "results")
        except Exception as e:
            print(f"FAILED: {e}")

        print("TinyFish fetch...", end=" ")
        try:
            r = tf_fetch(["https://example.com"])
            print("OK,", len(r.get("results", [])), "pages, errors:", r.get("errors"))
        except Exception as e:
            print(f"FAILED: {e}")
    elif config.TAVILY_API_KEY:
        print("Tavily search (fallback)...", end=" ")
        try:
            r = tf_search("test query")
            print("OK,", len(r.get("results", [])), "results")
        except Exception as e:
            print(f"FAILED: {e}")

        print("Tavily extract/fetch (fallback)...", end=" ")
        try:
            r = tf_fetch(["https://example.com"])
            print("OK,", len(r.get("results", [])), "pages, errors:", r.get("errors"))
        except Exception as e:
            print(f"FAILED: {e}")
    else:
        print("Search/Fetch: No TINYFISH_API_KEY or TAVILY_API_KEY configured!")

    # 2. LLM Check
    print("Testing LLM generation...")
    if config.OPENAI_API_KEY:
        print("  - OpenAI (gpt-4o-mini)...", end=" ")
        try:
            from .llm import _openai, parse_json
            r = parse_json(_openai("Return JSON.", 'Return {"ok": true}'))
            print("OK,", r)
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower():
                print("FAILED (OpenAI quota exhausted / 0 credits balance).")
                print("    -> Tip: Add billing credits at platform.openai.com, OR use a free Gemini/Groq key.")
            else:
                print(f"FAILED: {err[:140]}")

    if config.GEMINI_API_KEY:
        print("  - Google Gemini...", end=" ")
        try:
            from .llm import _gemini, parse_json
            r = parse_json(_gemini("Return JSON.", 'Return {"ok": true}'))
            print("OK,", r)
        except Exception as e:
            print(f"FAILED: {e}")

    if config.GROQ_API_KEY:
        print("  - Groq...", end=" ")
        try:
            from .llm import _groq, parse_json
            r = parse_json(_groq("Return JSON.", 'Return {"ok": true}'))
            print("OK,", r)
        except Exception as e:
            print(f"FAILED: {e}")

    if not (config.OPENAI_API_KEY or config.GEMINI_API_KEY or config.GROQ_API_KEY):
        print("  - No LLM keys configured in .env! (Set GEMINI_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY)")

    print("========================================")


if __name__ == "__main__":
    main()
