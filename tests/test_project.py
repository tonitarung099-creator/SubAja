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


def test_project_load_renumbers_duplicate_entry_ids(tmp_path: Path):
    session = tmp_path / "dup.subaja.json"
    session.write_text(
        """{
  "version": 1,
  "video_path": "",
  "srt_path": "",
  "entries": [
    {"index": 5, "start_ms": 0, "end_ms": 1000, "text": "A", "speaker": "", "speaker_confidence": 0.0, "original_text": "A", "source_index": 1, "review_reason": ""},
    {"index": 5, "start_ms": 1000, "end_ms": 2000, "text": "B", "speaker": "", "speaker_confidence": 0.0, "original_text": "B", "source_index": 2, "review_reason": ""}
  ]
}""",
        encoding="utf-8",
    )
    project = SubtitleProject()
    project.load_session(session)
    assert [e.index for e in project.entries] == [1, 2]


def test_project_save_leaves_no_temp_file(tmp_path: Path):
    project = SubtitleProject(entries=[SubtitleEntry(1, 0, 1000, "A", original_text="A", source_index=1)])
    session = tmp_path / "safe.subaja.json"
    project.save_session(session)
    assert session.is_file()
    assert not session.with_name(session.name + ".tmp").exists()


def test_corrupt_project_load_does_not_mutate_existing_state(tmp_path: Path):
    project = SubtitleProject(
        video_path=tmp_path / "old.mp4",
        srt_path=tmp_path / "old.srt",
        entries=[SubtitleEntry(1, 0, 1000, "Lama", original_text="Lama", source_index=1)],
    )
    bad = tmp_path / "bad.subaja.json"
    bad.write_text(
        """{
  "version": 1,
  "video_path": "C:/baru.mp4",
  "srt_path": "C:/baru.srt",
  "entries": [{"index": "rusak"}]
}""",
        encoding="utf-8",
    )

    try:
        project.load_session(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("Project rusak harus ditolak.")

    assert project.video_path == tmp_path / "old.mp4"
    assert project.srt_path == tmp_path / "old.srt"
    assert len(project.entries) == 1
    assert project.entries[0].text == "Lama"
