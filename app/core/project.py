from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .style import apply_reference_film_style
from .subtitle import SubtitleEntry, load_srt, save_srt


@dataclass
class SubtitleProject:
    video_path: Path | None = None
    srt_path: Path | None = None
    entries: list[SubtitleEntry] = field(default_factory=list)

    def load_video(self, path: str | Path):
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(p)
        self.video_path = p

    def load_srt(self, path: str | Path):
        p = Path(path)
        self.entries = load_srt(p)
        self.srt_path = p

    def export(
        self,
        path: str | Path,
        include_speaker: bool = False,
        reference_film_style: bool = True,
    ):
        entries = apply_reference_film_style(self.entries) if reference_film_style else self.entries
        save_srt(path, entries, include_speaker=include_speaker)
