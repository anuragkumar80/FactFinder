"""Chunk a fetched page and rank chunks against a claim with BM25.

BM25Plus is used (not Okapi) because it stays well-behaved on the tiny
corpora we have (a handful of chunks per page).
"""
import re
from rank_bm25 import BM25Plus

MAX_PAGE_CHARS = 60_000
MIN_CHUNK_CHARS = 40
STOPWORDS = set("""a an the and or but if of to in on at by for with from as is are was were be been
being it its this that these those he she they them his her their we you i not no do does did has have
had will would can could should may might about into over after before than then so such also""".split())


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower())
            if len(t) > 1 and t not in STOPWORDS]


def _split_long(piece: str, max_chars: int) -> list[str]:
    """Split an oversize paragraph at sentence boundaries, hard-slicing if needed."""
    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", piece):
        while len(sent) > max_chars:  # no punctuation at all: hard slice
            if cur:
                out.append(cur)
                cur = ""
            out.append(sent[:max_chars])
            sent = sent[max_chars:]
        if cur and len(cur) + 1 + len(sent) > max_chars:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_text(text: str, max_chars: int = 900) -> list[str]:
    """Paragraph-aware chunks of at most `max_chars` characters."""
    text = (text or "")[:MAX_PAGE_CHARS]
    pieces = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        pieces.extend([para] if len(para) <= max_chars else _split_long(para, max_chars))

    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 2 + len(p) > max_chars:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


def rank_chunks(query: str, chunks: list[str], k: int = 2) -> list[dict]:
    """Return the top-k chunks with positive BM25 score: [{chunk_id, text, score}]."""
    tokenized = [tokenize(c) for c in chunks]
    if not chunks or not any(tokenized):
        return []
    q = tokenize(query)
    if not q:
        return []
    scores = BM25Plus(tokenized).get_scores(q)
    order = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
    return [{"chunk_id": i, "text": chunks[i], "score": float(scores[i])}
            for i in order[:k] if scores[i] > 0]
