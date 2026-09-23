from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile


def get_ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError(
            "FFmpeg tidak tersedia. Paket imageio-ffmpeg harus terpasang."
        ) from exc


def extract_mono_wav(video_path: str | Path, output_path: str | Path | None = None) -> Path:
    video = Path(video_path)
    if not video.is_file():
        raise FileNotFoundError(video)
    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(prefix="subaja_", suffix=".wav", delete=False)
        tmp.close()
        output = Path(tmp.name)
    else:
        output = Path(output_path)
    cmd = [
        get_ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(output),
    ]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Gagal mengekstrak audio: {proc.stderr.strip()}")
        return output
    except Exception:
        try:
            output.unlink(missing_ok=True)
        except Exception:
            pass
        raise
