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
    def __init__(self):
        self.path = app_data_dir() / "cache.sqlite3"
        self.db = sqlite3.connect(self.path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS gemini_cache (k TEXT PRIMARY KEY, result TEXT NOT NULL)"
        )
        self.db.commit()

    @staticmethod
    def key(model: str, text: str) -> str:
        return hashlib.sha256((model + "\0" + text).encode("utf-8")).hexdigest()

    def get(self, model: str, text: str) -> str | None:
        row = self.db.execute("SELECT result FROM gemini_cache WHERE k=?", (self.key(model, text),)).fetchone()
        return row[0] if row else None

    def put(self, model: str, text: str, result: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO gemini_cache(k,result) VALUES (?,?)",
            (self.key(model, text), result),
        )
        self.db.commit()
