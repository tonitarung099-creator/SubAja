from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
import os

from .audio import extract_mono_wav
from .resources import model_paths
from .subtitle import SubtitleEntry, renumber
from .verbatim import has_formatting_markup, remove_dialogue_prefixes, split_entry_by_boundaries


@dataclass(slots=True)
class SpeakerSegment:
    start_ms: int
    end_ms: int
    speaker: str


def _overlap_ms(a0: int, a1: int, b0: int, b1: int) -> int:
    return max(0, min(a1, b1) - max(a0, b0))


class SpeakerDiarizer:
    def __init__(self, cluster_threshold: float = 0.75, num_speakers: int = -1):
        self.cluster_threshold = float(cluster_threshold)
        self.num_speakers = int(num_speakers) if int(num_speakers) > 0 else -1

    def _engine(self):
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise RuntimeError("sherpa-onnx belum tersedia di build ini.") from exc
        segmentation_model, embedding_model = model_paths()
        if not segmentation_model.is_file() or not embedding_model.is_file():
            raise RuntimeError(
                "Model speaker belum tersedia. Jalankan scripts/download_models.py lalu build ulang."
            )
        config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
            segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=str(segmentation_model), window_shift_ratio=0.1
                ),
                num_threads=max(1, min(4, (os.cpu_count() or 2) // 2)),
            ),
            embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(embedding_model),
                num_threads=max(1, min(4, (os.cpu_count() or 2) // 2)),
            ),
            clustering=sherpa_onnx.FastClusteringConfig(
                num_clusters=self.num_speakers,
                threshold=self.cluster_threshold,
            ),
            min_duration_on=0.30,
            min_duration_off=0.40,
        )
        if not config.validate():
            raise RuntimeError("Konfigurasi model diarization tidak valid.")
        return sherpa_onnx.OfflineSpeakerDiarization(config)

    def analyze_video(
        self,
        video_path: str | Path,
        progress: Callable[[int], None] | None = None,
    ) -> list[SpeakerSegment]:
        import soundfile as sf

        wav = extract_mono_wav(video_path)
        try:
            audio, sample_rate = sf.read(str(wav), dtype="float32", always_2d=True)
            audio = audio[:, 0]
            engine = self._engine()
            if sample_rate != engine.sample_rate:
                raise RuntimeError(f"Sample rate audio {sample_rate} != {engine.sample_rate}")

            def cb(done: int, total: int) -> int:
                if progress and total:
                    progress(min(99, int(done * 100 / total)))
                return 0

            result = engine.process(audio, callback=cb).sort_by_start_time()
            segments = [
                SpeakerSegment(
                    start_ms=int(round(r.start * 1000)),
                    end_ms=int(round(r.end * 1000)),
                    speaker=f"Speaker {int(r.speaker) + 1}",
                )
                for r in result
            ]
            if progress:
                progress(100)
            return segments
        finally:
            try:
                wav.unlink(missing_ok=True)
            except Exception:
                pass


def _segments_inside_entry(entry: SubtitleEntry, segments: Iterable[SpeakerSegment]) -> list[tuple[int, str, int]]:
    clipped: list[tuple[int, str, int]] = []
    for s in segments:
        overlap = _overlap_ms(entry.start_ms, entry.end_ms, s.start_ms, s.end_ms)
        if overlap <= 0:
            continue
        start = max(entry.start_ms, s.start_ms)
        end = min(entry.end_ms, s.end_ms)
        if end - start < 120:
            continue
        if clipped and clipped[-1][1] == s.speaker and start - clipped[-1][2] <= 160:
            old = clipped[-1]
            clipped[-1] = (old[0], old[1], end)
        else:
            clipped.append((start, s.speaker, end))
    return clipped


def apply_speaker_segments(
    entries: list[SubtitleEntry],
    segments: list[SpeakerSegment],
    split_on_change: bool = True,
) -> list[SubtitleEntry]:
    output: list[SubtitleEntry] = []
    for entry in entries:
        cleaned_text = remove_dialogue_prefixes(entry.text)
        entry = entry.clone(
            text=cleaned_text,
            speaker="",
            speaker_confidence=0.0,
            review_reason="",
        )
        overlaps = _segments_inside_entry(entry, segments)
        if not overlaps:
            output.append(
                entry.clone(
                    speaker="",
                    speaker_confidence=0.0,
                    review_reason="Tidak ada speaker yang terdeteksi pada rentang caption ini.",
                )
            )
            continue

        speaker_durations: dict[str, int] = {}
        for start, speaker, end in overlaps:
            speaker_durations[speaker] = speaker_durations.get(speaker, 0) + (end - start)
        dominant = max(speaker_durations, key=speaker_durations.get)
        confidence = speaker_durations[dominant] / max(1, sum(speaker_durations.values()))

        distinct = {x[1] for x in overlaps}
        has_speaker_overlap = any(
            overlaps[i][2] > overlaps[i + 1][0] + 80
            for i in range(len(overlaps) - 1)
        )
        safe_split = (
            split_on_change
            and not has_formatting_markup(entry.text)
            and not has_speaker_overlap
            and len(distinct) > 1
            and len(overlaps) <= 4
            and all((end - start) >= 420 for start, _, end in overlaps)
            and len(entry.text.replace("\n", " ").split()) >= len(overlaps) * 2
        )
        if safe_split:
            pieces = split_entry_by_boundaries(entry, overlaps)
            output.extend(
                p.clone(
                    speaker_confidence=0.75,
                    review_reason="Pergantian speaker terjadi di dalam satu caption CapCut; batas kata diperkirakan dari durasi suara.",
                )
                for p in pieces
            )
        else:
            reason = ""
            if len(distinct) > 1:
                if has_speaker_overlap:
                    reason = (
                        "Dua atau lebih speaker terdengar tumpang tindih pada caption ini. "
                        "Pemisahan otomatis ditahan agar timing dan kata tidak salah."
                    )
                elif has_formatting_markup(entry.text):
                    reason = (
                        "Ada lebih dari satu speaker dan caption memakai tag format seperti <i>. "
                        "Pemisahan otomatis ditahan agar tag tidak rusak."
                    )
                else:
                    reason = "Ada lebih dari satu speaker pada caption ini, tetapi pemisahan otomatis dinilai belum aman."
            output.append(entry.clone(speaker=dominant, speaker_confidence=confidence, review_reason=reason))
    return renumber(output)
