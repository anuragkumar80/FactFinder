from backend.verify import verify_quote, normalize

PAGE = """# Moon landing
NASA\u2019s **Apollo 11** mission landed the first humans on the Moon on [July 20, 1969](https://x.org).
Independent tracking stations around the world confirmed the mission.
"""


def test_exact_quote_passes():
    assert verify_quote("Independent tracking stations around the world confirmed the mission.", PAGE)


def test_formatting_differences_tolerated():
    assert verify_quote("NASA's Apollo 11 mission landed the first humans on the Moon on July 20, 1969", PAGE)


def test_fabricated_quote_fails():
    assert not verify_quote("NASA admitted the footage was filmed in a studio in Nevada.", PAGE)


def test_altered_words_fail():
    assert not verify_quote("Independent tracking stations around the world denied the mission.", PAGE)


def test_too_short_quote_fails():
    assert not verify_quote("the Moon", PAGE)


def test_ellipsis_fragments_must_all_exist():
    assert verify_quote("Apollo 11 mission landed the first humans ... tracking stations around the world", PAGE)
    assert not verify_quote("Apollo 11 mission landed the first humans ... secretly staged in a desert", PAGE)


def test_normalize_collapses_whitespace_and_case():
    assert normalize("  Hello\n\n WORLD ") == "hello world"
