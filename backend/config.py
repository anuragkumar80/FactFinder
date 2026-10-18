"""Loads settings from environment variables (never hard-code keys)."""
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Live Web & Search Providers
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
EXA_API_KEY = os.getenv("EXA_API_KEY", "")

# LLM Providers
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Observability
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")

MAX_CLAIM_CHARS = 1500
MAX_CLAIMS = 2
MAX_PAGES = 5  # distinct-domain pages fetched per claim

DB_PATH = os.getenv("DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "factfinder.db"))
CACHE_TTL_HOURS = float(os.getenv("CACHE_TTL_HOURS", "24"))
FETCH_DAILY_LIMIT = int(os.getenv("FETCH_DAILY_LIMIT", "900"))  # TinyFish free cap is 1,000/day; keep a margin
RATE_LIMIT_CHECKS = int(os.getenv("RATE_LIMIT_CHECKS", "6"))    # live checks per IP per window
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "600"))
