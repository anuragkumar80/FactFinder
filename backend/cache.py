"""SQLite storage: result cache (by claim hash) and the daily TinyFish usage counter."""
import hashlib
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import config

_USAGE_COLUMNS = {"searches", "fetches", "live_checks"}


@contextmanager
def db():
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS results (
            claim_hash TEXT PRIMARY KEY, input_text TEXT NOT NULL,
            result_json TEXT NOT NULL, created_at REAL NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS usage (
            day TEXT PRIMARY KEY, searches INTEGER NOT NULL DEFAULT 0,
            fetches INTEGER NOT NULL DEFAULT 0, live_checks INTEGER NOT NULL DEFAULT 0)""")
        yield conn
        conn.commit()
    finally:
        conn.close()


def claim_hash(text: str) -> str:
    """Hash of the normalised input (case and whitespace insensitive)."""
    norm = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def get_any(text: str) -> dict | None:
    """Latest stored result regardless of age: {result, created_at, age_seconds}."""
    with db() as conn:
        row = conn.execute("SELECT result_json, created_at FROM results WHERE claim_hash=?",
                           (claim_hash(text),)).fetchone()
    if not row:
        return None
    return {"result": json.loads(row[0]), "created_at": row[1],
            "age_seconds": max(0, int(time.time() - row[1]))}


def get_cached(text: str, ttl_hours: float | None = None) -> dict | None:
    """Like get_any, but None when older than the TTL."""
    ttl = (config.CACHE_TTL_HOURS if ttl_hours is None else ttl_hours) * 3600
    hit = get_any(text)
    return hit if hit and hit["age_seconds"] <= ttl else None


def put(text: str, result: dict) -> None:
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO results VALUES (?,?,?,?)",
                     (claim_hash(text), text, json.dumps(result, ensure_ascii=False, default=str),
                      time.time()))


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def add_usage(kind: str, n: int = 1) -> None:
    if kind not in _USAGE_COLUMNS:
        raise ValueError(kind)
    with db() as conn:
        conn.execute("INSERT OR IGNORE INTO usage(day) VALUES (?)", (_today(),))
        conn.execute(f"UPDATE usage SET {kind} = {kind} + ? WHERE day = ?", (n, _today()))


def get_quota() -> dict:
    with db() as conn:
        row = conn.execute("SELECT searches, fetches, live_checks FROM usage WHERE day=?",
                           (_today(),)).fetchone()
    searches, fetches, live = row if row else (0, 0, 0)
    return {"day": _today(), "searches": searches, "fetches": fetches, "live_checks": live,
            "fetch_limit": config.FETCH_DAILY_LIMIT,
            "fetch_remaining": max(0, config.FETCH_DAILY_LIMIT - fetches)}


def fetch_quota_exhausted() -> bool:
    """True when there may not be enough budget left for one more full live check."""
    needed = config.MAX_PAGES * config.MAX_CLAIMS
    return get_quota()["fetch_remaining"] < needed
