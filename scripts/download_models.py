from __future__ import annotations

import bz2
import io
from pathlib import Path
import shutil
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "assets" / "models"
SEG_DIR = MODELS / "segmentation"
SEG_FILE = SEG_DIR / "model.int8.onnx"
EMB_FILE = MODELS / "nemo_en_titanet_small.onnx"

SEG_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
EMB_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/nemo_en_titanet_small.onnx"


def download(url: str, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1024:
        print(f"exists: {dest}")
        return
    print(f"download: {url}")
    with urllib.request.urlopen(url, timeout=120) as r, dest.open("wb") as f:
        shutil.copyfileobj(r, f)


def main():
    MODELS.mkdir(parents=True, exist_ok=True)
    SEG_DIR.mkdir(parents=True, exist_ok=True)
    if not SEG_FILE.exists():
        archive = MODELS / "segmentation.tar.bz2"
        download(SEG_URL, archive)
        with tarfile.open(archive, "r:bz2") as tf:
            member = next(
                m for m in tf.getmembers()
                if m.name.endswith("/model.int8.onnx") or m.name == "model.int8.onnx"
            )
            source = tf.extractfile(member)
            if source is None:
                raise RuntimeError("model.int8.onnx tidak ditemukan di archive")
            with SEG_FILE.open("wb") as out:
                shutil.copyfileobj(source, out)
        archive.unlink(missing_ok=True)
        print(f"saved: {SEG_FILE}")
    download(EMB_URL, EMB_FILE)
    print("Models ready")


if __name__ == "__main__":
    main()
