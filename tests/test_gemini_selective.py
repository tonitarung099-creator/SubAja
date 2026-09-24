from types import SimpleNamespace

from app.core.gemini import (
    GeminiError,
    GeminiPunctuator,
    _cache_material,
    _normalize_batch_response,
    estimate_gemini_work,
    needs_gemini_punctuation,
)
from app.core.subtitle import SubtitleEntry


def make(text: str, review_reason: str = "") -> SubtitleEntry:
    return SubtitleEntry(
        1, 0, 2000, text,
        original_text=text,
        source_index=1,
        review_reason=review_reason,
    )


def test_gemini_skips_caption_that_already_looks_clean():
    assert not needs_gemini_punctuation(make("Aku mau pulang."))


def test_gemini_sends_caption_without_terminal_punctuation():
    assert needs_gemini_punctuation(make("aku mau pulang"))


def test_gemini_skips_clean_caption_with_speaker_only_review_warning():
    assert not needs_gemini_punctuation(make("Aku mau pulang.", review_reason="Speaker perlu dicek."))


def test_gemini_detects_indonesian_question_with_wrong_period():
    assert needs_gemini_punctuation(make("Kenapa kamu pergi."))


def test_gemini_work_estimate_uses_batches():
    entries = [make("aku mau pulang") for _ in range(61)]
    # Index duplication tidak memengaruhi estimator karena hanya menghitung kebutuhan.
    selected, requests = estimate_gemini_work(entries, batch_size=60)
    assert selected == 61
    assert requests == 2


def test_gemini_cache_material_changes_with_neighbor_context():
    a = [
        SubtitleEntry(1, 0, 1000, "Jangan pergi.", speaker="Speaker 1"),
        SubtitleEntry(2, 1000, 2000, "Apa", speaker="Speaker 2"),
        SubtitleEntry(3, 2000, 3000, "Aku tetap pergi.", speaker="Speaker 1"),
    ]
    b = [
        SubtitleEntry(1, 0, 1000, "Kamu dengar?", speaker="Speaker 1"),
        SubtitleEntry(2, 1000, 2000, "Apa", speaker="Speaker 2"),
        SubtitleEntry(3, 2000, 3000, "Tidak ada.", speaker="Speaker 1"),
    ]
    assert _cache_material(a, 1) != _cache_material(b, 1)


def test_gemini_detects_common_indonesian_question_particle_with_wrong_period():
    assert needs_gemini_punctuation(make("Kamu mau pergi nggak."))


def test_gemini_detects_ke_mana_question_with_wrong_period():
    assert needs_gemini_punctuation(make("Kamu mau ke mana."))


def test_gemini_batch_response_rejects_duplicate_known_id():
    data = [{"id": 1, "text": "A."}, {"id": 1, "text": "B."}]
    try:
        _normalize_batch_response(data, {1})
    except GeminiError as exc:
        assert "duplikat" in str(exc)
    else:
        raise AssertionError("ID Gemini duplikat harus ditolak.")


def test_gemini_batch_response_ignores_unknown_ids():
    data = [{"id": 99, "text": "asing"}, {"id": 2, "text": "Benar."}]
    assert _normalize_batch_response(data, {2}) == {2: "Benar."}


class _FakeModels:
    def __init__(self, owner, text):
        self.owner = owner
        self.text = text

    def generate_content(self, **kwargs):
        assert self.owner.entered is True
        assert self.owner.closed is False
        return SimpleNamespace(text=self.text)


class _FakeClient:
    def __init__(self, text="OK"):
        self.entered = False
        self.closed = False
        self.models = _FakeModels(self, text)

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.closed = True


def test_gemini_test_holds_client_open_until_request_finishes(monkeypatch):
    punctuator = GeminiPunctuator("test-key", "gemini-3.8-flash")
    fake = _FakeClient("OK")
    monkeypatch.setattr(punctuator, "_client", lambda: fake)

    assert punctuator.test() == "OK"
    assert fake.entered is True
    assert fake.closed is True


def test_gemini_batch_holds_client_open_until_request_finishes(monkeypatch):
    punctuator = GeminiPunctuator("test-key", "gemini-3.8-flash")
    fake = _FakeClient('[{"id":1,"text":"Aku pulang."}]')
    monkeypatch.setattr(punctuator, "_client", lambda: fake)

    result = punctuator._call_batch([make("Aku pulang.")])
    assert result == {1: "Aku pulang."}
    assert fake.entered is True
    assert fake.closed is True
