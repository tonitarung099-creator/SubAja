import sqlite3

from app.core.cache import GeminiCache


def test_gemini_cache_falls_back_to_memory_when_sqlite_cannot_open(monkeypatch, tmp_path):
    monkeypatch.setattr("app.core.cache.app_data_dir", lambda: tmp_path)

    def fail_connect(*args, **kwargs):
        raise sqlite3.OperationalError("database locked")

    monkeypatch.setattr(sqlite3, "connect", fail_connect)

    cache = GeminiCache()
    assert cache.db is None
    assert cache.get("model", "teks") is None

    cache.put("model", "teks", "hasil")
    assert cache.get("model", "teks") == "hasil"


def test_gemini_cache_close_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setattr("app.core.cache.app_data_dir", lambda: tmp_path)
    cache = GeminiCache()
    cache.put("model", "teks", "hasil")
    cache.close()
    cache.close()
    assert cache.db is None
    assert cache.get("model", "teks") == "hasil"
