from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from .cache import GeminiCache
from .subtitle import SubtitleEntry, renumber
from .verbatim import is_verbatim_safe, visible_text, wrap_two_lines


class GeminiError(RuntimeError):
    pass


class GeminiQuotaError(GeminiError):
    pass


_CACHE_CONTEXT_VERSION = "gemini-punctuation-v2"


@dataclass(slots=True)
class GeminiStats:
    processed: int = 0
    cached: int = 0
    rejected_word_changes: int = 0
    missing_results: int = 0
    skipped_clean: int = 0


def needs_gemini_punctuation(entry: SubtitleEntry) -> bool:
    """Hemat Free Tier: kirim hanya caption yang masih tampak perlu bantuan AI."""
    flat = " ".join(entry.text.replace("\n", " ").split()).strip()
    visible = " ".join(visible_text(entry.text).replace("\n", " ").split()).strip()
    if not visible:
        return False
    if entry.review_reason:
        return True

    first_alpha = next((ch for ch in visible if ch.isalpha()), "")
    starts_clean = not first_alpha or first_alpha.isupper()
    ends_clean = visible.endswith((".", "?", "!", "…", '."', '?"', '!"', ".”", "?”", "!”"))
    spacing_clean = "  " not in entry.text and " ," not in entry.text and " ." not in entry.text

    # Kalimat tanya bahasa Indonesia sering ditranskrip CapCut sebagai titik biasa.
    # Tandai untuk Gemini hanya bila ada sinyal tanya yang cukup kuat.
    lower = visible.casefold()
    question_starters = (
        "apa ", "apakah ", "siapa ", "kapan ", "kenapa ", "mengapa ",
        "bagaimana ", "berapa ", "mana ", "di mana ", "dimana ",
        "ke mana ", "kemana ", "dari mana ", "darimana ",
    )
    question_particles = (" nggak?", " tidak?", " kan?", " ya?")
    looks_like_question = (
        lower.startswith(question_starters)
        or any(token in lower for token in (" kenapa ", " bagaimana ", " berapa ", " siapa ", " kapan "))
        or lower.endswith(question_particles)
    )
    if looks_like_question and not visible.endswith(("?", '?"', "?”")):
        return True

    return not (starts_clean and ends_clean and spacing_clean)


def _cache_material(entries: list[SubtitleEntry], pos: int) -> str:
    entry = entries[pos]
    prev_text = entries[pos - 1].text if pos > 0 else ""
    next_text = entries[pos + 1].text if pos + 1 < len(entries) else ""
    return "\0".join(
        (
            _CACHE_CONTEXT_VERSION,
            entry.speaker or "",
            prev_text,
            entry.text,
            next_text,
        )
    )


def estimate_gemini_work(entries: list[SubtitleEntry], batch_size: int = 60) -> tuple[int, int]:
    selected = sum(1 for e in entries if needs_gemini_punctuation(e))
    requests = (selected + max(1, batch_size) - 1) // max(1, batch_size)
    return selected, requests


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


class GeminiPunctuator:
    def __init__(self, api_key: str, model: str = "gemini-3.8-flash"):
        if not api_key.strip():
            raise GeminiError("API key Gemini belum dipilih.")
        self.api_key = api_key.strip()
        self.model = model.strip() or "gemini-3.8-flash"
        self.cache = GeminiCache()

    def _client(self):
        try:
            from google import genai
        except ImportError as exc:
            raise GeminiError("Paket google-genai tidak tersedia.") from exc
        return genai.Client(api_key=self.api_key)

    @staticmethod
    def _low_thinking_config():
        try:
            from google.genai import types
        except ImportError as exc:
            raise GeminiError("Paket google-genai tidak tersedia.") from exc
        return types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level="low")
        )

    def test(self) -> str:
        try:
            response = self._client().models.generate_content(
                model=self.model,
                contents="Balas hanya dengan kata OK.",
                config=self._low_thinking_config(),
            )
            return (response.text or "").strip()
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg.upper():
                raise GeminiQuotaError("Kuota/rate limit Gemini tercapai.") from exc
            raise GeminiError(msg) from exc

    def _call_batch(self, entries: list[SubtitleEntry]) -> dict[int, str]:
        payload = [{"id": e.index, "speaker": e.speaker or None, "text": e.text} for e in entries]
        prompt = (
            "Anda adalah editor tanda baca subtitle film Indonesia.\n"
            "ATURAN MUTLAK:\n"
            "1. JANGAN menambah, menghapus, mengganti, meringkas, menerjemahkan, atau mengubah urutan SATU KATA PUN.\n"
            "2. Yang boleh diubah HANYA huruf besar/kecil, tanda baca, spasi, dan pemisahan baris.\n"
            "3. Pertahankan kata informal persis seperti sumber: nggak tetap nggak, udah tetap udah, dll.\n"
            "4. Gunakan pergantian speaker hanya sebagai konteks untuk menentukan tanda baca; jangan menulis label speaker ke teks.\n"
            "5. Jangan menggabungkan, menghapus, atau memecah ID subtitle.\n"
            "6. Kembalikan JSON array saja dengan bentuk [{\"id\":1,\"text\":\"...\"}].\n"
            "7. Maksimal dua baris per subtitle.\n"
            "8. Pertahankan tag format SRT/ASS seperti <i>...</i>, <b>...</b>, atau {\\...} PERSIS seperti sumber.\n"
            "9. Jika subtitle memiliki dua baris yang diawali tanda - untuk dua pembicara, pertahankan dua baris dan tanda - tersebut PERSIS.\n\n"
            "SUBTITLE:\n" + json.dumps(payload, ensure_ascii=False)
        )
        try:
            response = self._client().models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._low_thinking_config(),
            )
            data = _extract_json(response.text or "")
            return {int(x["id"]): str(x["text"]) for x in data if "id" in x and "text" in x}
        except Exception as exc:
            msg = str(exc)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg.upper():
                raise GeminiQuotaError(
                    "Kuota/rate limit Gemini tercapai. Proses dihentikan aman; hasil yang sudah selesai tersimpan di cache."
                ) from exc
            raise GeminiError(msg) from exc

    def process(
        self,
        entries: list[SubtitleEntry],
        batch_size: int = 30,
        progress: Callable[[int, str], None] | None = None,
    ) -> tuple[list[SubtitleEntry], GeminiStats]:
        out = [e.clone() for e in entries]
        stats = GeminiStats()
        missing: list[SubtitleEntry] = []
        positions: dict[int, int] = {}
        cache_materials: dict[int, str] = {}

        for pos, e in enumerate(out):
            positions[e.index] = pos
            cache_materials[e.index] = _cache_material(out, pos)
            if not needs_gemini_punctuation(e):
                stats.skipped_clean += 1
                continue
            cached = self.cache.get(self.model, cache_materials[e.index])
            if cached is not None and is_verbatim_safe(e.text, cached):
                out[pos] = e.clone(text=cached)
                stats.cached += 1
            else:
                missing.append(e)

        total = max(1, len(missing))
        if not missing:
            if progress:
                progress(100, f"Gemini hemat: 0 dikirim, {stats.skipped_clean} sudah rapi")
            return renumber(out), stats
        done = 0
        for offset in range(0, len(missing), batch_size):
            batch = missing[offset : offset + batch_size]
            results = self._call_batch(batch)
            for e in batch:
                if e.index not in results:
                    stats.missing_results += 1
                    stats.processed += 1
                    done += 1
                    continue

                candidate = results[e.index]
                # Absolute word lock. Gemini output is discarded if one lexical token changes.
                if is_verbatim_safe(e.text, candidate):
                    candidate = wrap_two_lines(candidate, max_chars=42)
                    out[positions[e.index]] = e.clone(text=candidate)
                    self.cache.put(self.model, cache_materials[e.index], candidate)
                else:
                    stats.rejected_word_changes += 1
                stats.processed += 1
                done += 1
            if progress:
                progress(int(done * 100 / total), f"Gemini: {done}/{len(missing)}")
        return renumber(out), stats
