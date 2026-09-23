from app.core.qc import audit_entries, changed_source_indices, source_group_is_safe
from app.core.subtitle import SubtitleEntry


def test_qc_detects_word_change_across_split_source():
    entries = [
        SubtitleEntry(1, 0, 1000, "aku sudah", original_text="aku sudah pergi", source_index=1),
        SubtitleEntry(2, 1000, 2000, "pulang", original_text="aku sudah pergi", source_index=1),
    ]
    assert changed_source_indices(entries) == {1}
    assert not source_group_is_safe(entries, 1)
    results = audit_entries(entries)
    assert results[0].level == "critical"
    assert "WORD" in results[0].codes


def test_qc_accepts_verbatim_split():
    entries = [
        SubtitleEntry(1, 0, 1500, "aku sudah", original_text="aku sudah pergi", source_index=1),
        SubtitleEntry(2, 1500, 3000, "pergi", original_text="aku sudah pergi", source_index=1),
    ]
    assert source_group_is_safe(entries, 1)
    assert 1 not in changed_source_indices(entries)


def test_qc_marks_estimated_speaker_boundary_for_review():
    e = SubtitleEntry(
        1, 0, 2000, "aku sudah pergi", speaker="Speaker 1", speaker_confidence=0.75,
        original_text="aku sudah pergi", source_index=1,
        review_reason="Batas kata diperkirakan.",
    )
    result = audit_entries([e])[0]
    assert result.level == "review"
    assert "SPEAKER" in result.codes
