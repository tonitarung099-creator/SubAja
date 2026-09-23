from app.core.subtitle import SubtitleEntry
from app.core.speaker import SpeakerSegment, apply_speaker_segments
from app.core.verbatim import lexical_tokens


def test_apply_speaker_segments_preserves_words():
    entries = [SubtitleEntry(1, 0, 4000, "aku sudah bilang kamu jangan pergi")]
    segments = [
        SpeakerSegment(0, 2000, "Speaker 1"),
        SpeakerSegment(2000, 4000, "Speaker 2"),
    ]
    out = apply_speaker_segments(entries, segments, split_on_change=True)
    assert len(out) == 2
    assert out[0].speaker == "Speaker 1"
    assert out[1].speaker == "Speaker 2"
    assert lexical_tokens(entries[0].text) == lexical_tokens(" ".join(x.text for x in out))


def test_overlapping_speakers_are_not_auto_split():
    entry = SubtitleEntry(
        1, 0, 4000, "aku pulang kamu tunggu di sini",
        original_text="aku pulang kamu tunggu di sini",
        source_index=1,
    )
    segments = [
        SpeakerSegment(0, 2400, "Speaker 1"),
        SpeakerSegment(1800, 4000, "Speaker 2"),
    ]
    out = apply_speaker_segments([entry], segments, split_on_change=True)
    assert len(out) == 1
    assert "tumpang tindih" in out[0].review_reason


def test_reanalysis_clears_stale_speaker_when_no_segment_matches():
    entry = SubtitleEntry(
        1, 1000, 2000, "Aku pulang.",
        speaker="Speaker 9",
        speaker_confidence=0.99,
        original_text="Aku pulang.",
        source_index=1,
    )
    out = apply_speaker_segments([entry], [], split_on_change=True)
    assert len(out) == 1
    assert out[0].speaker == ""
    assert out[0].speaker_confidence == 0.0
    assert "Tidak ada speaker" in out[0].review_reason


def test_repeated_speaker_analysis_does_not_keep_splitting_previous_pieces():
    entry = SubtitleEntry(
        1,
        0,
        4000,
        "aku sudah bilang kamu jangan pergi",
        original_text="aku sudah bilang kamu jangan pergi",
        source_index=1,
    )
    segments = [
        SpeakerSegment(0, 2000, "Speaker 1"),
        SpeakerSegment(2000, 4000, "Speaker 2"),
    ]

    first = apply_speaker_segments([entry], segments, split_on_change=True)
    second = apply_speaker_segments(first, segments, split_on_change=True)

    assert len(first) == 2
    assert len(second) == 2
    assert [x.speaker for x in second] == ["Speaker 1", "Speaker 2"]
    assert lexical_tokens(" ".join(x.text for x in first)) == lexical_tokens(
        " ".join(x.text for x in second)
    )
    assert second[0].start_ms == 0
    assert second[-1].end_ms == 4000
