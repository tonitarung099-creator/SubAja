from app.core.gemini import needs_gemini_punctuation
from app.core.subtitle import SubtitleEntry


def make(text: str, review_reason: str = "") -> SubtitleEntry:
    return SubtitleEntry(
        1, 0, 2000, text,
        original_text=text,
        source_index=1,
        review_reason=review_reason,
    )


def test_gemini_skips_caption_that_already_looks_clean():
    assert not needs_gemini_punctuation(make("Aku mau pulang."))


def test_gemini_sends_caption_without_terminal_punctuation():
    assert needs_gemini_punctuation(make("aku mau pulang"))


def test_gemini_sends_caption_marked_for_review():
    assert needs_gemini_punctuation(make("Aku mau pulang.", review_reason="Speaker perlu dicek."))
