from core.utils.utilities import clip_to_width, text_width


def test_latin_text_counts_one_per_character():
    assert text_width("Spotify") == 7


def test_full_width_characters_count_as_two():
    assert text_width("東京") == 4
    assert text_width("ｈｉ") == 4  # full-width Latin letters
    assert text_width("한국어") == 6


def test_mixed_text_adds_both_widths():
    assert text_width("Song - 夜に駆ける") == 7 + 10


def test_clip_keeps_text_that_fits():
    assert clip_to_width("abc", 3) == "abc"
    assert clip_to_width("東京", 4) == "東京"


def test_clip_cuts_latin_text_at_the_width():
    assert clip_to_width("abcdef", 3) == "abc"


def test_clip_never_splits_a_full_width_character():
    # The third column would land in the middle of 京
    assert clip_to_width("東京", 3) == "東"


def test_clip_to_zero_is_empty():
    assert clip_to_width("abc", 0) == ""
    assert clip_to_width("abc", -1) == ""
