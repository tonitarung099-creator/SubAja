from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .subtitle import SubtitleEntry, renumber

_WORD_RE = re.compile(r"[\wÀ-ÖØ-öø-ÿ]+(?:['’\-][\wÀ-ÖØ-öø-ÿ]+)*", re.UNICODE)
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
_SPACE_AFTER_PUNCT = re.compile(r"([,.;:!?])(?!\s|$)")
_MULTI_SPACE = re.compile(r"[ \t]+")


def lexical_tokens(text: str) -> list[str]:
    return [m.group(0).casefold() for m in _WORD_RE.finditer(text)]


def is_verbatim_safe(original: str, candidate: str) -> bool:
    """True when lexical words are identical and in the same order.

    Case, punctuation, whitespace, and line breaks may change. Words may not.
    """
    return lexical_tokens(original) == lexical_tokens(candidate)


def clean_spacing(text: str) -> str:
    lines = []
    for line in text.replace("\r", "").split("\n"):
        line = _MULTI_SPACE.sub(" ", line.strip())
        line = _SPACE_BEFORE_PUNCT.sub(r"\1", line)
        line = _SPACE_AFTER_PUNCT.sub(r"\1 ", line)
        lines.append(line.strip())
    return "\n".join(x for x in lines if x)


def capitalize_first(text: str) -> str:
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch.isalpha():
            chars[i] = ch.upper()
            break
    return "".join(chars)


def ensure_terminal_punctuation(text: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return stripped
    if stripped[-1] in ".!?…,:;-'\"”’":
        return stripped
    return stripped + "."


def wrap_two_lines(text: str, max_chars: int = 42) -> str:
    """Wrap to at most two visually balanced lines without changing words."""
    flat = " ".join(text.replace("\n", " ").split())
    if len(flat) <= max_chars:
        return flat
    words = flat.split(" ")
    if len(words) <= 1:
        return flat
    best = None
    for cut in range(1, len(words)):
        left = " ".join(words[:cut])
        right = " ".join(words[cut:])
        overflow = max(0, len(left) - max_chars) + max(0, len(right) - max_chars)
        balance = abs(len(left) - len(right))
        score = overflow * 1000 + balance
        if best is None or score < best[0]:
            best = (score, left, right)
    assert best is not None
    return best[1] + "\n" + best[2]


def tidy_local(text: str, add_terminal_punctuation: bool = False, max_chars: int = 42) -> str:
    original = text
    out = clean_spacing(text)
    out = capitalize_first(out)
    if add_terminal_punctuation:
        out = ensure_terminal_punctuation(out)
    out = wrap_two_lines(out, max_chars=max_chars)
    # Hard safety guard: no lexical word may be changed by the local formatter.
    if not is_verbatim_safe(original, out):
        return original
    return out


def split_words_preserving(text: str) -> list[str]:
    # Dialogue cue bergaya film memakai "- " di awal baris. Tanda itu hanya
    # formatting, bukan kata sumber, jadi jangan ikut dibagi saat diarization
    # dijalankan ulang.
    without_dialogue_prefix = re.sub(r"(?m)^\\s*-\\s+", "", text)
    return without_dialogue_prefix.replace("\n", " ").split()


def split_entry_by_boundaries(
    entry: SubtitleEntry,
    boundaries: list[tuple[int, str, int]],
) -> list[SubtitleEntry]:
    """Split one subtitle using speaker time boundaries.

    boundaries: [(start_ms, speaker, end_ms), ...] clipped to this subtitle.
    Words are assigned proportionally to duration and are never edited.
    """
    if len(boundaries) <= 1:
        speaker = boundaries[0][1] if boundaries else entry.speaker
        return [entry.clone(speaker=speaker)]

    words = split_words_preserving(entry.text)
    if len(words) < len(boundaries):
        # Too little text to split safely; use dominant speaker only.
        dominant = max(boundaries, key=lambda x: x[2] - x[0])
        return [entry.clone(speaker=dominant[1])]

    durations = [max(1, end - start) for start, _, end in boundaries]
    total_dur = sum(durations)
    raw_counts = [len(words) * d / total_dur for d in durations]
    counts = [max(1, int(v)) for v in raw_counts]

    # Adjust counts to exact word total while keeping every segment non-empty.
    while sum(counts) > len(words):
        idx = max((i for i, c in enumerate(counts) if c > 1), key=lambda i: counts[i], default=None)
        if idx is None:
            break
        counts[idx] -= 1
    while sum(counts) < len(words):
        idx = max(range(len(counts)), key=lambda i: raw_counts[i] - counts[i])
        counts[idx] += 1

    result: list[SubtitleEntry] = []
    cursor = 0
    for (start, speaker, end), count in zip(boundaries, counts):
        piece_words = words[cursor : cursor + count]
        cursor += count
        if not piece_words:
            continue
        piece = " ".join(piece_words)
        result.append(
            entry.clone(
                start_ms=start,
                end_ms=end,
                text=piece,
                speaker=speaker,
                speaker_confidence=1.0,
            )
        )
    if cursor < len(words) and result:
        result[-1] = result[-1].clone(text=result[-1].text + " " + " ".join(words[cursor:]))
    # Verify exact lexical preservation. If anything went wrong, refuse the split.
    joined = " ".join(x.text for x in result)
    if not is_verbatim_safe(entry.text, joined):
        return [entry]
    return result


def tidy_entries(entries: Iterable[SubtitleEntry], max_chars: int = 42) -> list[SubtitleEntry]:
    return renumber(e.clone(text=tidy_local(e.text, max_chars=max_chars)) for e in entries)
