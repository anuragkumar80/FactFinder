"""Quote verification: an LLM quote counts only if it appears in the fetched text.

This is the anti-hallucination guard. Both sides are normalised (case, quotes,
dashes, whitespace, markdown links) so harmless formatting differences do not
cause false rejections, but the words themselves must match.
"""
import re
import unicodedata

_TRANSLATE = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-", "\u00a0": " ",
})
MIN_QUOTE_CHARS = 20
MIN_FRAGMENT_CHARS = 8


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").translate(_TRANSLATE)
    s = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", s)  # markdown links/images -> text
    s = re.sub(r"[*_`#>|~]", "", s)                  # markdown decoration
    return re.sub(r"\s+", " ", s).strip().lower()


def verify_quote(quote: str, page_text: str) -> bool:
    """True if `quote` is found verbatim (after normalisation) in `page_text`.

    A quote containing an ellipsis is split into fragments; every fragment
    must be found. Very short quotes are rejected as too weak to be evidence.
    """
    nq = normalize(quote)
    if len(nq) < MIN_QUOTE_CHARS:
        return False
    page = normalize(page_text)
    fragments = [f.strip(" .") for f in re.split(r"\.{3,}|\u2026", nq)]
    fragments = [f for f in fragments if f]
    if not fragments or any(len(f) < MIN_FRAGMENT_CHARS for f in fragments):
        return False
    return all(f in page for f in fragments)
