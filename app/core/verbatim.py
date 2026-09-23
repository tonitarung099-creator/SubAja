from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .subtitle import SubtitleEntry, renumber

_WORD_RE = re.compile(r"[\wÀ-ÖØ-öø-ÿ]+(?:['’\-][\wÀ-ÖØ-öø-ÿ]+)*", re.UNICODE)
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")
_SPACE_AFTER_PUNCT = re.compile(r"([,.;:!?])(?!\s|$)")
_MULTI_SPACE = re.compile(r"[ \t]+")
_MARKUP_RE = re.compile(r"(<[^>\r\n]+>|\{\\[^}\r\n]*\})")


def formatting_markup(text: str) -> list[str]:
    """Return formatting tags/overrides in source order.

    SRT HTML tags such as <i> and ASS-style {\\...} overrides are formatting,
    not spoken words, but SubAja preserves them exactly so styling is not lost.
    """
    return [m.group(0) for m in _MARKUP_RE.finditer(text)]


def visible_text(text: str) -> str:
    return _MARKUP_RE.sub("", text)


def visible_length(text: str) -> int:
    return len(visible_text(text))


def has_formatting_markup(text: str) -> bool:
    return _MARKUP_RE.search(text) is not None


def lexical_tokens(text: str) -> list[str]:
    return [m.group(0).casefold() for m in _WORD_RE.finditer(visible_text(text))]


def formatting_signature(text: str) -> list[tuple[str, int]]:
    """Lock every formatting tag to the same spoken-word boundary."""
    signature: list[tuple[str, int]] = []
    for match in _MARKUP_RE.finditer(text):
        words_before = len(lexical_tokens(text[: match.start()]))
        signature.append((match.group(0), words_before))
    return signature


def dialogue_structure(text: str) -> tuple[int, ...]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    prefixed = tuple(i for i, line in enumerate(lines) if line.startswith("- "))
    return prefixed if len(prefixed) >= 2 else ()


def remove_dialogue_prefixes(text: str) -> str:
    """Remove film-style '- ' speaker markers without changing spoken words."""
    if not dialogue_structure(text):
        return text
    return " ".join(
        re.sub(r"^\s*-\s+", "", line).strip()
        for line in text.splitlines()
        if line.strip()
    )


def preserves_dialogue_structure(original: str, candidate: str) -> bool:
    signature = dialogue_structure(original)
    if not signature:
        return True
    candidate_lines = [line.strip() for line in candidate.splitlines() if line.strip()]
    candidate_signature = tuple(i for i, line in enumerate(candidate_lines) if line.startswith("- "))
    original_lines = [line.strip() for line in original.splitlines() if line.strip()]
    return candidate_signature == signature and len(candidate_lines) == len(original_lines)


def is_verbatim_safe(original: str, candidate: str) -> bool:
    """True when lexical words are identical and in the same order.

    Case, punctuation, whitespace, and line breaks may change. Words may not.
    """
    return (
        lexical_tokens(original) == lexical_tokens(candidate)
        and formatting_signature(original) == formatting_signature(candidate)
        and preserves_dialogue_structure(original, candidate)
    )


def clean_spacing(text: str) -> str:
    lines = []
    for line in text.replace("\r", "").split("\n"):
        line = _MULTI_SPACE.sub(" ", line.strip())
        line = _SPACE_BEFORE_PUNCT.sub(r"\1", line)
        line = _SPACE_AFTER_PUNCT.sub(r"\1 ", line)
        lines.append(line.strip())
    return "\n".join(x for x in lines if x)


def capitalize_first(text: str) -> str:
    # Never capitalize letters inside formatting tags such as <i>.
    parts = _MARKUP_RE.split(text)
    for part_index, part in enumerate(parts):
        if not part or _MARKUP_RE.fullmatch(part):
            continue
        chars = list(part)
        for i, ch in enumerate(chars):
            if ch.isalpha():
                chars[i] = ch.upper()
                parts[part_index] = "".join(chars)
                return "".join(parts)
    return text


def ensure_terminal_punctuation(text: str) -> str:
    stripped = text.rstrip()
    if not stripped:
        return stripped

    visible = visible_text(stripped).rstrip()
    if not visible or visible[-1] in ".!?…,:;-'\"”’":
        return stripped

    # Put punctuation before trailing formatting tags:
    # <i>Aku pulang</i> -> <i>Aku pulang.</i>
    trailing: list[str] = []
    body = stripped
    while True:
        match = re.search(r"(<\/[^>\r\n]+>|\{\\[^}\r\n]*\})$", body)
        if not match:
            break
        trailing.insert(0, match.group(0))
        body = body[: match.start()].rstrip()
    return body + "." + "".join(trailing)

def wrap_two_lines(text: str, max_chars: int = 42) -> str:
    """Wrap to at most two visually balanced lines without changing words."""
    if dialogue_structure(text):
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
    flat = " ".join(text.replace("\n", " ").split())
    if visible_length(flat) <= max_chars:
        return flat
    words = flat.split(" ")
    if len(words) <= 1:
        return flat
    best = None
    for cut in range(1, len(words)):
        left = " ".join(words[:cut])
        right = " ".join(words[cut:])
        left_len = visible_length(left)
        right_len = visible_length(right)
        overflow = max(0, left_len - max_chars) + max(0, right_len - max_chars)
        balance = abs(left_len - right_len)
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
    without_dialogue_prefix = re.sub(r"(?m)^\s*-\s+", "", text)
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
