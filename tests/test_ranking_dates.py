from datetime import date
from backend.ranking import chunk_text, rank_chunks
from backend.dates import extract_date

TODAY = date(2026, 10, 17)


def test_chunks_respect_max_and_drop_junk():
    text = "Menu\n\n" + ("This is a long sentence about vaccines. " * 100)
    chunks = chunk_text(text, max_chars=300)
    assert chunks and all(len(c) <= 300 for c in chunks)
    assert all(len(c) >= 40 for c in chunks)  # 'Menu' dropped


def test_hard_slice_when_no_punctuation():
    chunks = chunk_text("x" * 2500, max_chars=900)
    assert all(len(c) <= 900 for c in chunks) and len(chunks) == 3


def test_rank_puts_relevant_chunk_first():
    chunks = ["The recipe needs two cups of flour and a pinch of salt for the bread dough.",
              "Apollo 11 landed astronauts on the Moon in July 1969 according to NASA records.",
              "Our newsletter covers gardening tips and seasonal planting guides for spring."]
    top = rank_chunks("Apollo 11 Moon landing 1969", chunks, k=2)
    assert top[0]["chunk_id"] == 1


def test_rank_handles_empty_and_no_match():
    assert rank_chunks("anything", []) == []
    assert rank_chunks("zzzqqq", ["completely unrelated words here about bread and flour baking"]) == []


def test_date_with_marker():
    assert extract_date("Intro text\n\nPublished: October 3, 2026\n\nBody", TODAY) == date(2026, 10, 3)


def test_date_iso_and_dmy():
    assert extract_date("By Staff | 2026-09-30 | News", TODAY) == date(2026, 9, 30)
    assert extract_date("Posted 5 March 2025 by admin", TODAY) == date(2025, 3, 5)


def test_unmarked_late_date_is_ignored():
    text = ("word " * 400) + "The treaty was signed on June 4, 1999 in Geneva."
    assert extract_date(text, TODAY) is None


def test_future_and_invalid_dates_ignored():
    assert extract_date("Published: December 25, 2030", TODAY) is None
    assert extract_date("Published: 2026-02-31", TODAY) is None


def test_no_date_returns_none():
    assert extract_date("No dates anywhere in this text.", TODAY) is None
