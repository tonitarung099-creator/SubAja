from __future__ import annotations

from pathlib import Path
import hashlib
import os
import sqlite3


def app_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.getenv("APPDATA") or Path.home())
    else:
        root = Path.home() / ".config"
    path = root / "SubAja"
    path.mkdir(parents=True, exist_ok=True)
    return path


class GeminiCache:
    """Persistent Gemini cache with safe in-memory fallback.

    Cache is an optimization only. A corrupt/locked/read-only SQLite file must
    never prevent subtitle processing from continuing.
    """

    def __init__(self):
        self.path = app_data_dir() / "cache.sqlite3"
        self.db: sqlite3.Connection | None = None
        self.memory: dict[str, str] = {}
        self._open()

    def _open(self) -> None:
        try:
            db = sqlite3.connect(self.path, timeout=10.0)
            db.execute("PRAGMA busy_timeout = 10000")
            db.execute(
                "CREATE TABLE IF NOT EXISTS gemini_cache (k TEXT PRIMARY KEY, result TEXT NOT NULL)"
            )
            db.commit()
            self.db = db
        except (sqlite3.Error, OSError):
            try:
                if self.db is not None:
                    self.db.close()
            except Exception:
                pass
            self.db = None

    @staticmethod
    def key(model: str, text: str) -> str:
        return hashlib.sha256((model + "\0" + text).encode("utf-8")).hexdigest()

    def get(self, model: str, text: str) -> str | None:
        key = self.key(model, text)
        if key in self.memory:
            return self.memory[key]
        if self.db is None:
            return None
        try:
            row = self.db.execute(
                "SELECT result FROM gemini_cache WHERE k=?", (key,)
            ).fetchone()
            return row[0] if row else None
        except sqlite3.Error:
            return None

    def put(self, model: str, text: str, result: str) -> None:
        key = self.key(model, text)
        self.memory[key] = result
        if self.db is None:
            return
        try:
            self.db.execute(
                "INSERT OR REPLACE INTO gemini_cache(k,result) VALUES (?,?)",
                (key, result),
            )
            self.db.commit()
        except sqlite3.Error:
            # Cache persistence failure must never fail the Gemini job.
            pass

    def close(self) -> None:
        if self.db is not None:
            try:
                self.db.close()
            finally:
                self.db = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
