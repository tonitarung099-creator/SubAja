from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .subtitle import SubtitleEntry
from .verbatim import is_verbatim_safe


@dataclass(slots=True)
class QCResult:
    level: str  # ok | review | critical
    codes: tuple[str, ...]
    message: str

    @property
    def label(self) -> str:
        return {"ok": "OK", "review": "CEK", "critical": "KRITIS"}.get(self.level, self.level.upper())


def changed_source_indices(entries: Iterable[SubtitleEntry]) -> set[int]:
    groups: dict[int, list[SubtitleEntry]] = {}
    for e in entries:
        if e.source_index is None:
            continue
        groups.setdefault(int(e.source_index), []).append(e)

    changed: set[int] = set()
    for source_index, parts in groups.items():
        parts = sorted(parts, key=lambda x: (x.start_ms, x.index))
        original = parts[0].original_text
        joined = " ".join(p.text.replace("\n", " ").strip() for p in parts if p.text.strip())
        if original and not is_verbatim_safe(original, joined):
            changed.add(source_index)
    return changed


def source_group_is_safe(entries: Iterable[SubtitleEntry], source_index: int | None) -> bool:
    if source_index is None:
        return True
    parts = [e for e in entries if e.source_index == source_index]
    if not parts:
        return True
    parts.sort(key=lambda x: (x.start_ms, x.index))
    original = parts[0].original_text
    joined = " ".join(p.text.replace("\n", " ").strip() for p in parts if p.text.strip())
    return not original or is_verbatim_safe(original, joined)


def audit_entry(
    entry: SubtitleEntry,
    *,
    next_entry: SubtitleEntry | None = None,
    source_changed: bool = False,
    speaker_analysis_present: bool = False,
    max_chars_per_line: int = 42,
    max_cps: float = 20.0,
) -> QCResult:
    critical: list[str] = []
    review: list[str] = []
    messages: list[str] = []

    if source_changed:
        critical.append("WORD")
        messages.append("Kata berubah dari transkrip CapCut (Word Lock gagal).")

    duration = entry.duration_ms
    flat = " ".join(entry.text.replace("\n", " ").split())
    lines = [x for x in entry.text.splitlines() if x.strip()] or [flat]

    if duration < 500:
        review.append("DURASI")
        messages.append("Durasi subtitle sangat pendek (<0,5 dtk).")
    elif duration > 8000:
        review.append("DURASI")
        messages.append("Durasi subtitle sangat panjang (>8 dtk).")

    if duration > 0:
        visible_chars = len(flat.replace(" ", ""))
        cps = visible_chars / (duration / 1000.0)
        if cps > max_cps:
            review.append("CPS")
            messages.append(f"Kecepatan baca tinggi ({cps:.1f} karakter/dtk).")

    if len(lines) > 2:
        review.append("BARIS")
        messages.append("Lebih dari 2 baris.")
    if any(len(line) > max_chars_per_line for line in lines):
        review.append("PANJANG")
        messages.append(f"Ada baris lebih dari {max_chars_per_line} karakter.")

    if next_entry is not None and entry.end_ms > next_entry.start_ms:
        review.append("OVERLAP")
        messages.append("Timing bertumpuk dengan subtitle berikutnya.")

    if entry.review_reason:
        review.append("SPEAKER")
        messages.append(entry.review_reason)
    elif speaker_analysis_present and entry.speaker and 0 < entry.speaker_confidence < 0.65:
        review.append("SPEAKER")
        messages.append(f"Keyakinan speaker rendah ({entry.speaker_confidence:.0%}).")
    elif speaker_analysis_present and not entry.speaker:
        review.append("SPEAKER")
        messages.append("Speaker belum teridentifikasi.")

    if critical:
        level = "critical"
        codes = tuple(dict.fromkeys(critical + review))
    elif review:
        level = "review"
        codes = tuple(dict.fromkeys(review))
    else:
        level = "ok"
        codes = ()
        messages = ["Tidak ada masalah QC yang terdeteksi."]

    return QCResult(level=level, codes=codes, message="\n".join(dict.fromkeys(messages)))


def audit_entries(entries: list[SubtitleEntry]) -> list[QCResult]:
    changed = changed_source_indices(entries)
    speaker_analysis_present = any(e.speaker for e in entries)
    results: list[QCResult] = []
    for i, entry in enumerate(entries):
        nxt = entries[i + 1] if i + 1 < len(entries) else None
        results.append(
            audit_entry(
                entry,
                next_entry=nxt,
                source_changed=entry.source_index in changed if entry.source_index is not None else False,
                speaker_analysis_present=speaker_analysis_present,
            )
        )
    return results
