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
