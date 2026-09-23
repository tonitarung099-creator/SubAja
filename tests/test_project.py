from pathlib import Path

from app.core.project import SubtitleProject
from app.core.subtitle import SubtitleEntry


def test_project_session_round_trip(tmp_path: Path):
    p = SubtitleProject(
        video_path=tmp_path / "film.mp4",
        srt_path=tmp_path / "film.srt",
        entries=[
            SubtitleEntry(
                1, 1000, 2500, "Aku pulang.",
                speaker="Speaker 1",
                speaker_confidence=0.9,
                original_text="aku pulang",
                source_index=1,
                review_reason="",
            )
        ],
    )
    session = tmp_path / "film.subaja.json"
    p.save_session(session)

    restored = SubtitleProject()
    restored.load_session(session)

    assert restored.video_path == p.video_path
    assert restored.srt_path == p.srt_path
    assert len(restored.entries) == 1
    assert restored.entries[0].text == "Aku pulang."
    assert restored.entries[0].speaker == "Speaker 1"
    assert restored.project_path == session
