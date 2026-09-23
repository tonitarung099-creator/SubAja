from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json

from .qc import changed_source_indices
from .style import apply_reference_film_style
from .subtitle import SubtitleEntry, load_srt, renumber, save_srt


def _validated_project_entry(item: dict) -> SubtitleEntry:
    if not isinstance(item, dict):
        raise ValueError("entry subtitle bukan object JSON.")

    entry = SubtitleEntry(**item)

    if not isinstance(entry.index, int) or isinstance(entry.index, bool):
        raise ValueError("index subtitle harus integer.")
    if not isinstance(entry.start_ms, int) or isinstance(entry.start_ms, bool):
        raise ValueError("start_ms subtitle harus integer.")
    if not isinstance(entry.end_ms, int) or isinstance(entry.end_ms, bool):
        raise ValueError("end_ms subtitle harus integer.")
    if entry.start_ms < 0 or entry.end_ms <= entry.start_ms:
        raise ValueError("rentang waktu subtitle tidak valid.")
    if not isinstance(entry.text, str) or not entry.text.strip():
        raise ValueError("text subtitle harus string dan tidak boleh kosong.")
    if not isinstance(entry.original_text, str):
        raise ValueError("original_text subtitle harus string.")
    if not isinstance(entry.speaker, str):
        raise ValueError("speaker subtitle harus string.")
    if isinstance(entry.speaker_confidence, bool) or not isinstance(entry.speaker_confidence, (int, float)):
        raise ValueError("speaker_confidence harus angka.")
    entry.speaker_confidence = float(entry.speaker_confidence)
    if not 0.0 <= entry.speaker_confidence <= 1.0:
        raise ValueError("speaker_confidence harus antara 0 dan 1.")
    if entry.source_index is not None and (
        not isinstance(entry.source_index, int) or isinstance(entry.source_index, bool)
    ):
        raise ValueError("source_index harus integer atau null.")
    if not isinstance(entry.review_reason, str):
        raise ValueError("review_reason subtitle harus string.")

    return entry


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
        encoded = json.dumps(payload, ensure_ascii=False, indent=2)
        tmp = p.with_name(p.name + ".tmp")
        try:
            tmp.write_text(encoded, encoding="utf-8")
            tmp.replace(p)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
        self.project_path = p

    def load_session(self, path: str | Path):
        p = Path(path)
        payload = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Project SubAja rusak: format utama harus object JSON.")

        version = int(payload.get("version", 1))
        if version != 1:
            raise ValueError(f"Versi project SubAja belum didukung: {version}.")

        raw_entries = payload.get("entries", [])
        if not isinstance(raw_entries, list):
            raise ValueError("Project SubAja rusak: entries bukan daftar.")

        # Bangun seluruh state di variabel sementara. Jangan menyentuh project
        # aktif bila satu entry saja rusak.
        new_video_path = Path(payload["video_path"]) if payload.get("video_path") else None
        new_srt_path = Path(payload["srt_path"]) if payload.get("srt_path") else None
        try:
            new_entries = renumber(_validated_project_entry(item) for item in raw_entries)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Project SubAja rusak: data subtitle tidak valid ({exc}).") from exc

        self.video_path = new_video_path
        self.srt_path = new_srt_path
        self.entries = new_entries
        self.project_path = p

    def export(
        self,
        path: str | Path,
        include_speaker: bool = False,
        reference_film_style: bool = True,
    ):
        entries = apply_reference_film_style(self.entries) if reference_film_style else self.entries
        changed = changed_source_indices(entries)
        if changed:
            raise ValueError(
                f"Export diblokir: Word Lock gagal setelah styling pada {len(changed)} caption sumber."
            )
        save_srt(path, entries, include_speaker=include_speaker)
