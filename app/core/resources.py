from __future__ import annotations

from pathlib import Path
import sys


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base / relative


def model_paths() -> tuple[Path, Path]:
    segmentation = resource_path("assets/models/segmentation/model.int8.onnx")
    embedding = resource_path("assets/models/nemo_en_titanet_small.onnx")
    return segmentation, embedding
