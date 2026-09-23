from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re
from typing import Iterable

_TIME_RE = re.compile(r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{3})")
_TIMING_LINE_RE = re.compile(
    r"^\s*(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})(?:\s+.*)?$"
)


@dataclass(slots=True)
class SubtitleEntry:
    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker: str = ""
    speaker_confidence: float = 0.0
    original_text: str = ""
    source_index: int | None = None
    review_reason: str = ""

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def clone(self, **changes) -> "SubtitleEntry":
        return replace(self, **changes)


def timestamp_to_ms(value: str) -> int:
    m = _TIME_RE.fullmatch(value.strip())
    if not m:
        raise ValueError(f"Invalid SRT timestamp: {value!r}")
    return (
        int(m.group("h")) * 3_600_000
        + int(m.group("m")) * 60_000
        + int(m.group("s")) * 1_000
        + int(m.group("ms"))
    )


def ms_to_timestamp(value: int) -> str:
    value = max(0, int(round(value)))
    h, rem = divmod(value, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(text: str) -> list[SubtitleEntry]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    if not normalized.strip():
        return []

    blocks = re.split(r"\n\s*\n", normalized.strip())
    entries: list[SubtitleEntry] = []

    for block_number, block in enumerate(blocks, 1):
        lines = block.split("\n")
        if len(lines) < 2:
            raise ValueError(f"Blok SRT #{block_number} tidak lengkap.")

        idx_text = lines[0].strip()
        if not idx_text.isdigit():
            raise ValueError(
                f"Blok SRT #{block_number} memiliki nomor cue tidak valid: {idx_text!r}."
            )

        timing = _TIMING_LINE_RE.fullmatch(lines[1])
        if timing is None:
            raise ValueError(
                f"Blok SRT #{block_number} memiliki timing tidak valid: {lines[1]!r}."
            )

        idx = int(idx_text)
        raw = "\n".join(lines[2:]).strip("\n")
        entries.append(
            SubtitleEntry(
                index=idx,
                start_ms=timestamp_to_ms(timing.group("start")),
                end_ms=timestamp_to_ms(timing.group("end")),
                text=raw,
                original_text=raw,
                source_index=idx,
            )
        )

    return entries

def load_srt(path: str | Path) -> list[SubtitleEntry]:
    p = Path(path)
    data = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return parse_srt(data.decode(enc))
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("srt", data, 0, 1, "Unsupported encoding")


def renumber(entries: Iterable[SubtitleEntry]) -> list[SubtitleEntry]:
    out: list[SubtitleEntry] = []
    for i, e in enumerate(entries, 1):
        out.append(e.clone(index=i))
    return out


def dump_srt(entries: Iterable[SubtitleEntry], include_speaker: bool = False) -> str:
    blocks: list[str] = []
    for i, entry in enumerate(entries, 1):
        text = entry.text.strip()
        if include_speaker and entry.speaker:
            text = f"[{entry.speaker}] {text}"
        blocks.append(
            f"{i}\n{ms_to_timestamp(entry.start_ms)} --> {ms_to_timestamp(entry.end_ms)}\n{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def save_srt(path: str | Path, entries: Iterable[SubtitleEntry], include_speaker: bool = False) -> None:
    Path(path).write_text(dump_srt(entries, include_speaker=include_speaker), encoding="utf-8-sig")
