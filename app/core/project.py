from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from .style import apply_reference_film_style
from .subtitle import SubtitleEntry, load_srt, save_srt


@dataclass
class SubtitleProject:
    video_path: Path | None = None
    srt_path: Path | None = None
    entries: list[SubtitleEntry] = field(default_factory=list)
    project_path: Path | None = None

    def load_video(self, path: str | Path):
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(p)
        self.video_path = p

    def load_srt(self, path: str | Path):
        p = Path(path)
        self.entries = load_srt(p)
        self.srt_path = p
        self.project_path = None

    def save_session(self, path: str | Path):
        p = Path(path)
        payload = {
            "version": 1,
            "video_path": str(self.video_path) if self.video_path else "",
            "srt_path": str(self.srt_path) if self.srt_path else "",
            "entries": [asdict(e) for e in self.entries],
        }
        p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.project_path = p

    def load_session(self, path: str | Path):
        p = Path(path)
        payload = json.loads(p.read_text(encoding="utf-8"))
        self.video_path = Path(payload["video_path"]) if payload.get("video_path") else None
        self.srt_path = Path(payload["srt_path"]) if payload.get("srt_path") else None
        self.entries = [SubtitleEntry(**item) for item in payload.get("entries", [])]
        self.project_path = p

    def export(
        self,
        path: str | Path,
        include_speaker: bool = False,
        reference_film_style: bool = True,
    ):
        entries = apply_reference_film_style(self.entries) if reference_film_style else self.entries
        save_srt(path, entries, include_speaker=include_speaker)
