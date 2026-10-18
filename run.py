"""Convenience entrypoint to run FactFinder from the project root."""
import os
import sys
from pathlib import Path

# Ensure FactFinder package root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR / "FactFinder" if (BASE_DIR / "FactFinder").exists() else BASE_DIR

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

os.chdir(str(REPO_DIR))


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print("""FactFinder Commands:
  python run.py                     Start the Web Application (http://localhost:8000)
  python run.py --port 8080         Start Web App on custom port (e.g. 8080)
  python run.py --prewarm           Pre-warm SQLite cache with demo claims (<1s instant demo)
  python run.py --test              Run the complete pytest test suite (52 tests)
  python run.py --check             Test and verify all API keys (TinyFish, Tavily, OpenAI)
  python run.py --cli "claim text"  Verify a statement directly from the terminal
""")
        sys.exit(0)
    elif "--test" in args or "-t" in args:
        import pytest
        sys.exit(pytest.main([]))
    elif "--check" in args or "-c" in args:
        from backend.check_keys import main as check_main
        check_main()
    elif "--prewarm" in args or "-p" in args:
        from backend.prewarm import main as prewarm_main
        prewarm_main()
    elif "--cli" in args:
        from backend.cli import main as cli_main
        sys.argv = [sys.argv[0]] + [a for a in args if a != "--cli"]
        cli_main()
    else:
        import uvicorn
        port = 8000
        for i, a in enumerate(args):
            if a in ("--port", "-p") and i + 1 < len(args):
                port = int(args[i + 1])
        print(f"Starting FactFinder at http://localhost:{port}")
        uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=True)


if __name__ == "__main__":
    main()
