from app.core.gemini import needs_gemini_punctuation
from app.core.speaker import SpeakerSegment, apply_speaker_segments
from app.core.subtitle import SubtitleEntry
from app.core.verbatim import (
    dialogue_structure,
    formatting_markup,
    formatting_signature,
    is_verbatim_safe,
    lexical_tokens,
    split_words_preserving,
    tidy_local,
)


def test_italic_tag_is_not_counted_as_spoken_word_and_is_preserved():
    src = "<i>aku pulang</i>"
    out = tidy_local(src, add_terminal_punctuation=True)
    assert out == "<i>Aku pulang.</i>"
    assert lexical_tokens(src) == ["aku", "pulang"]
    assert formatting_markup(out) == ["<i>", "</i>"]
    assert is_verbatim_safe(src, out)
    assert not is_verbatim_safe(src, "Aku pulang.")


def test_ass_override_tag_is_recognized_and_preserved():
    src = r"{\i1}aku pulang{\i0}"
    assert formatting_markup(src) == [r"{\i1}", r"{\i0}"]
    assert lexical_tokens(src) == ["aku", "pulang"]
    assert is_verbatim_safe(src, r"{\i1}Aku pulang.{\i0}")


def test_dialogue_prefix_is_not_treated_as_word_when_resplitting():
    assert split_words_preserving("- Aku pulang.\n- Kenapa?") == ["Aku", "pulang.", "Kenapa?"]


def test_clean_italic_subtitle_is_skipped_by_gemini_saver():
    entry = SubtitleEntry(
        1, 0, 2000, "<i>Aku pulang.</i>",
        original_text="<i>Aku pulang.</i>", source_index=1,
    )
    assert not needs_gemini_punctuation(entry)


def test_formatted_caption_with_multiple_speakers_is_not_auto_split():
    entry = SubtitleEntry(
        1, 0, 4000, "<i>Aku pulang sekarang kamu tunggu di sini</i>",
        original_text="<i>Aku pulang sekarang kamu tunggu di sini</i>",
        source_index=1,
    )
    segments = [
        SpeakerSegment(0, 2000, "Speaker 1"),
        SpeakerSegment(2000, 4000, "Speaker 2"),
    ]
    out = apply_speaker_segments([entry], segments, split_on_change=True)
    assert len(out) == 1
    assert out[0].text == entry.text
    assert "tag format" in out[0].review_reason


def test_two_speaker_dialogue_structure_is_part_of_word_lock():
    src = "- Aku pulang.\n- Kenapa?"
    assert dialogue_structure(src) == (0, 1)
    assert is_verbatim_safe(src, "- Aku pulang!\n- Kenapa?")
    assert not is_verbatim_safe(src, "Aku pulang! Kenapa?")
    assert not is_verbatim_safe(src, "Aku pulang!\n- Kenapa?")


def test_word_lock_rejects_moved_italic_scope():
    src = "<i>Aku</i> pulang."
    moved = "<i>Aku pulang.</i>"
    assert formatting_signature(src) != formatting_signature(moved)
    assert not is_verbatim_safe(src, moved)
