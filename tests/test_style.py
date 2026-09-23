from app.core.style import REFERENCE_FILM_STYLE, apply_reference_film_style
from app.core.subtitle import SubtitleEntry
from app.core.verbatim import lexical_tokens


def test_reference_style_matches_two_speaker_dialogue_shape():
    original = "Asalamualaikum Wa alaikumsalam"
    entries = [
        SubtitleEntry(
            1, 1000, 2000, "Asalamualaikum.", speaker="Speaker 1",
            original_text=original, source_index=1,
        ),
        SubtitleEntry(
            2, 2000, 3000, "Wa alaikumsalam.", speaker="Speaker 2",
            original_text=original, source_index=1,
        ),
    ]
    out = apply_reference_film_style(entries)
    assert len(out) == 1
    assert out[0].text == "- Asalamualaikum.\n- Wa alaikumsalam."
    assert lexical_tokens(original) == lexical_tokens(out[0].text)


def test_reference_style_keeps_long_dialogue_separate_when_line_would_exceed_42():
    original = "aku punya kalimat yang sangat panjang sekali untuk dibaca kamu menjawab singkat"
    entries = [
        SubtitleEntry(
            1, 0, 2500, "aku punya kalimat yang sangat panjang sekali untuk dibaca",
            speaker="Speaker 1", original_text=original, source_index=7,
        ),
        SubtitleEntry(
            2, 2500, 4000, "kamu menjawab singkat",
            speaker="Speaker 2", original_text=original, source_index=7,
        ),
    ]
    out = apply_reference_film_style(entries)
    assert len(out) == 2
    assert all(len(line) <= REFERENCE_FILM_STYLE.max_chars_per_line or len(line.split()) == 1
               for e in out for line in e.text.splitlines())
    assert lexical_tokens(original) == lexical_tokens(" ".join(e.text for e in out))
