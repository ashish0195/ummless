"""Thin, timeout-guarded wrappers around ffmpeg/ffprobe."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import wave

import numpy as np

SAMPLE_RATE = 16_000
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


class AudioDecodeError(Exception):
    """The input could not be decoded as audio."""


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(args, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - pathological inputs
        raise AudioDecodeError("Audio processing timed out") from exc
    except FileNotFoundError as exc:  # pragma: no cover - deployment error
        raise AudioDecodeError("ffmpeg is not installed") from exc


def probe_duration(path: str) -> float | None:
    result = _run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        timeout=30,
    )
    if result.returncode != 0:
        return None
    try:
        return float(json.loads(result.stdout or b"{}")["format"]["duration"])
    except (KeyError, ValueError, TypeError):
        return None


def decode_to_wav16k(src: str, dst: str, max_seconds: float | None = None) -> None:
    """Decode any supported input to 16 kHz mono 16-bit PCM WAV."""
    args = [FFMPEG, "-nostdin", "-y", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE)]
    if max_seconds:
        args += ["-t", f"{max_seconds:.3f}"]
    args += ["-sample_fmt", "s16", "-f", "wav", dst]
    result = _run(args, timeout=600)
    if result.returncode != 0:
        raise AudioDecodeError(result.stderr.decode("utf-8", "replace")[-500:] or "decode failed")
    with wave.open(dst, "rb") as handle:
        if handle.getnframes() == 0:
            raise AudioDecodeError("No audio frames")


def read_wav(path: str) -> np.ndarray:
    """Read a 16-bit mono WAV as float32 in [-1, 1]."""
    with wave.open(path, "rb") as handle:
        frames = handle.readframes(handle.getnframes())
        channels = handle.getnchannels()
    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples


def wav_bytes(samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def write_wav(path: str, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    with open(path, "wb") as handle:
        handle.write(wav_bytes(samples, sample_rate))


def encode_mp3(src: str, dst: str, bitrate: str = "48k") -> None:
    """Compact mono MP3 for upload to the transcription API (25 MB request limit)."""
    result = _run(
        [FFMPEG, "-nostdin", "-y", "-v", "error", "-i", src, "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-c:a", "libmp3lame", "-b:a", bitrate, dst],
        timeout=600,
    )
    if result.returncode != 0:
        raise AudioDecodeError(result.stderr.decode("utf-8", "replace")[-500:] or "encode failed")


def cut_clip(src: str, dst: str, start: float, end: float) -> None:
    """Cut [start, end] seconds into an AAC .m4a clip suitable for in-app playback."""
    start = max(0.0, start)
    duration = max(0.3, end - start)
    result = _run(
        [FFMPEG, "-nostdin", "-y", "-v", "error", "-ss", f"{start:.3f}", "-i", src, "-t", f"{duration:.3f}",
         "-ac", "1", "-ar", "24000", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", dst],
        timeout=120,
    )
    if result.returncode != 0:
        raise AudioDecodeError(result.stderr.decode("utf-8", "replace")[-500:] or "clip failed")


def segment_samples(samples: np.ndarray, start: float, end: float) -> np.ndarray:
    a = max(0, int(start * SAMPLE_RATE))
    b = min(len(samples), int(end * SAMPLE_RATE))
    return samples[a:b] if b > a else samples[:0]
