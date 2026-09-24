from __future__ import annotations

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / "assets" / "subaja-logo.png"
ICO = ROOT / "assets" / "subaja.ico"


def main() -> None:
    if not PNG.is_file():
        raise FileNotFoundError(f"Logo PNG tidak ditemukan: {PNG}")

    with Image.open(PNG) as image:
        image.load()
        rgba = image.convert("RGBA")
        rgba.save(
            ICO,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32)],
        )

    with Image.open(ICO) as check:
        check.verify()

    print(f"Icon Windows siap: {ICO}")


if __name__ == "__main__":
    main()
