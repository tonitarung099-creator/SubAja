from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path

from .cache import app_data_dir


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))), buf


def _protect_windows(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob, _buf = _blob(data)
    out_blob = DATA_BLOB()
    if not crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _unprotect_windows(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob, _buf = _blob(data)
    out_blob = DATA_BLOB()
    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0, ctypes.byref(out_blob)):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _protect(data: bytes) -> bytes:
    if os.name == "nt":
        return _protect_windows(data)
    return data


def _unprotect(data: bytes) -> bytes:
    if os.name == "nt":
        return _unprotect_windows(data)
    return data


class KeyVault:
    MAX_KEYS = 100

    def __init__(self):
        self.path = app_data_dir() / "keys.json"
        self.data = {"active": 0, "model": "gemini-3.8-flash", "keys": [""] * self.MAX_KEYS}
        self.load()

    def load(self):
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            keys = []
            for item in raw.get("keys", [])[: self.MAX_KEYS]:
                if not item:
                    keys.append("")
                    continue
                keys.append(_unprotect(base64.b64decode(item)).decode("utf-8"))
            keys += [""] * (self.MAX_KEYS - len(keys))
            self.data = {
                "active": max(0, min(self.MAX_KEYS - 1, int(raw.get("active", 0)))),
                "model": str(raw.get("model") or "gemini-3.8-flash"),
                "keys": keys,
            }
        except Exception:
            # Corrupt settings should not stop the app from opening.
            pass

    def save(self):
        payload = {
            "active": self.active_index,
            "model": self.model,
            "keys": [base64.b64encode(_protect(k.encode("utf-8"))).decode("ascii") if k else "" for k in self.keys],
        }
        encoded = json.dumps(payload, indent=2)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            tmp.write_text(encoded, encoding="utf-8")
            tmp.replace(self.path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass

    @property
    def keys(self) -> list[str]:
        return self.data["keys"]

    @property
    def active_index(self) -> int:
        return int(self.data["active"])

    @active_index.setter
    def active_index(self, value: int):
        self.data["active"] = max(0, min(self.MAX_KEYS - 1, int(value)))

    @property
    def active_key(self) -> str:
        return self.keys[self.active_index].strip()

    @property
    def model(self) -> str:
        return str(self.data["model"])

    @model.setter
    def model(self, value: str):
        self.data["model"] = value.strip() or "gemini-3.8-flash"
