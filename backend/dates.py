"""Conservative publication-date extraction. We never guess.

A date is accepted only if (a) it sits right after a marker such as
'Published' / 'Updated' in the first 3,000 characters, or (b) it appears in the
first 600 characters (typical byline area). Otherwise the date is unknown.
"""
import re
from datetime import date

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MON = (r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
        r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
_MDY = re.compile(_MON + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+((?:19|20)\d{2})\b", re.I)
_DMY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+" + _MON + r"\.?,?\s+((?:19|20)\d{2})\b", re.I)
_MARKER = re.compile(r"(published|updated|posted|modified|last reviewed|date)\W{0,12}$", re.I)
SCAN_CHARS = 3000
BYLINE_CHARS = 600


def _candidates(text: str):
    for m in _ISO.finditer(text):
        yield m.start(), (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    for m in _MDY.finditer(text):
        yield m.start(), (int(m.group(3)), _MONTHS[m.group(1)[:3].lower()], int(m.group(2)))
    for m in _DMY.finditer(text):
        yield m.start(), (int(m.group(3)), _MONTHS[m.group(2)[:3].lower()], int(m.group(1)))


def extract_date(text: str, today: date | None = None) -> date | None:
    today = today or date.today()
    head = (text or "")[:SCAN_CHARS]
    marked, early = [], []
    for pos, (y, mo, d) in sorted(_candidates(head)):
        try:
            dt = date(y, mo, d)
        except ValueError:
            continue
        if dt > today:  # future dates are never publication dates
            continue
        if _MARKER.search(head[max(0, pos - 20):pos]):
            marked.append(dt)
        elif pos < BYLINE_CHARS:
            early.append(dt)
    if marked:
        return max(marked)  # 'Updated' beats 'Published' when both are present
    return early[0] if early else None
