from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .subtitle import SubtitleEntry, renumber
from .verbatim import capitalize_first, clean_spacing, is_verbatim_safe, tidy_local, visible_length


@dataclass(frozen=True, slots=True)
class FilmSubtitleStyle:
    name: str = "Film Indonesia - Referensi"
    max_chars_per_line: int = 42
    max_cps: float = 19.0
    max_lines: int = 2
    dialogue_prefix: str = "- "
    max_dialogue_cue_ms: int = 7000


REFERENCE_FILM_STYLE = FilmSubtitleStyle()


def _single_line(text: str) -> str:
    return capitalize_first(clean_spacing(" ".join(text.replace("\n", " ").split())))


def _format_single_entry(entry: SubtitleEntry, style: FilmSubtitleStyle) -> SubtitleEntry:
    lines = [line.strip() for line in entry.text.splitlines() if line.strip()]
    if len(lines) == 2 and all(line.startswith(style.dialogue_prefix) for line in lines):
        formatted_lines = []
        for line in lines:
            body = line[len(style.dialogue_prefix):]
            formatted_lines.append(style.dialogue_prefix + _single_line(body))
        candidate = "\n".join(formatted_lines)
        if (
            all(visible_length(line) <= style.max_chars_per_line for line in formatted_lines)
            and is_verbatim_safe(entry.text, candidate)
        ):
            return entry.clone(text=candidate)
    return entry.clone(text=tidy_local(entry.text, max_chars=style.max_chars_per_line))


def apply_reference_film_style(
    entries: Iterable[SubtitleEntry],
    style: FilmSubtitleStyle = REFERENCE_FILM_STYLE,
) -> list[SubtitleEntry]:
    """Format subtitle seperti SRT referensi film Indonesia.

    - Maksimal 2 baris dan 42 karakter per baris.
    - Jika SATU caption sumber CapCut dipecah menjadi tepat dua speaker,
      gabungkan kembali sebagai dialogue cue:
        - pembicara pertama
        - pembicara kedua
    - Tidak pernah menambah, menghapus, mengganti, atau mengubah urutan kata.
    """
    src = list(entries)
    out: list[SubtitleEntry] = []
    i = 0

    while i < len(src):
        current = src[i]
        group = [current]
        j = i + 1
        while (
            j < len(src)
            and current.source_index is not None
            and src[j].source_index == current.source_index
        ):
            group.append(src[j])
            j += 1

        if len(group) == 2:
            first, second = group
            a = _single_line(first.text)
            b = _single_line(second.text)
            different_speakers = bool(first.speaker and second.speaker and first.speaker != second.speaker)
            line_a = style.dialogue_prefix + a
            line_b = style.dialogue_prefix + b
            duration = max(first.end_ms, second.end_ms) - min(first.start_ms, second.start_ms)

            if (
                different_speakers
                and visible_length(line_a) <= style.max_chars_per_line
                and visible_length(line_b) <= style.max_chars_per_line
                and duration <= style.max_dialogue_cue_ms
            ):
                combined = line_a + "\n" + line_b
                original = first.original_text or second.original_text
                if not original or is_verbatim_safe(original, combined):
                    out.append(
                        first.clone(
                            start_ms=min(first.start_ms, second.start_ms),
                            end_ms=max(first.end_ms, second.end_ms),
                            text=combined,
                            speaker=f"{first.speaker} | {second.speaker}",
                            speaker_confidence=min(first.speaker_confidence, second.speaker_confidence),
                            review_reason="",
                        )
                    )
                    i = j
                    continue

        for entry in group:
            out.append(_format_single_entry(entry, style))
        i = j

    return renumber(out)
