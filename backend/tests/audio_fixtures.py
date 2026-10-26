"""Synthetic, speech-like audio for tests (no real voices needed).

Syllables are harmonic tones shaped by two vowel formants, grouped into words and phrases with pauses.
Different "speakers" differ in pitch and formant scaling, which is enough for VAD, quality checks,
the mock diarizer and the voiceprint conflict check to behave realistically.
"""

from __future__ import annotations

import os
import subprocess
import tempfile

import numpy as np

SR = 16_000
VOWELS = [(730, 1090), (270, 2290), (530, 1840), (300, 870), (660, 1720), (440, 1020), (490, 1350)]


def _db_to_amp(db: float) -> float:
    return 10 ** (db / 20)


def synth_speech(seconds: float, f0: float = 130.0, formant_scale: float = 1.0, level_db: float = -24.0,
                 seed: int = 0, noise_db: float = -72.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out: list[np.ndarray] = []
    total = 0
    target = int(seconds * SR)
    while total < target:
        # a phrase of 3–8 words
        for _ in range(int(rng.integers(3, 9))):
            for _ in range(int(rng.integers(1, 4))):  # syllables per word
                dur = rng.uniform(0.12, 0.26)
                n = int(dur * SR)
                t = np.arange(n) / SR
                pitch = f0 * (1 + 0.06 * np.sin(2 * np.pi * rng.uniform(2, 5) * t)) * rng.uniform(0.92, 1.08)
                phase = 2 * np.pi * np.cumsum(pitch) / SR
                f1, f2 = VOWELS[int(rng.integers(len(VOWELS)))]
                f1, f2 = f1 * formant_scale, f2 * formant_scale
                signal = np.zeros(n)
                for k in range(1, int(3800 / f0)):
                    freq = k * f0
                    amp = np.exp(-((freq - f1) / 180) ** 2) + 0.6 * np.exp(-((freq - f2) / 260) ** 2) + 0.03
                    signal += amp * np.sin(k * phase)
                envelope = np.sin(np.pi * np.linspace(0, 1, n)) ** 0.7
                out.append(signal * envelope)
                out.append(np.zeros(int(rng.uniform(0.02, 0.06) * SR)))
            out.append(np.zeros(int(rng.uniform(0.06, 0.14) * SR)))  # between words
        out.append(np.zeros(int(rng.uniform(0.35, 0.8) * SR)))  # between phrases
        total = sum(len(x) for x in out)
    audio = np.concatenate(out)[:target]
    speech_rms = np.sqrt(np.mean(audio[np.abs(audio) > 1e-6] ** 2)) if np.any(np.abs(audio) > 1e-6) else 1.0
    audio = audio / (speech_rms + 1e-9) * _db_to_amp(level_db)
    audio += rng.normal(0, _db_to_amp(noise_db), size=audio.shape)
    return audio.astype(np.float32)


def silence(seconds: float, noise_db: float = -72.0, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0, _db_to_amp(noise_db), size=int(seconds * SR)).astype(np.float32)


SPEAKERS = {
    "low": {"f0": 115.0, "formant_scale": 1.0},
    "high": {"f0": 215.0, "formant_scale": 1.17},
    "mid": {"f0": 165.0, "formant_scale": 1.08},
}


def synth_conversation(turns: list[tuple[str, float]], gap: float = 0.7, seed: int = 0,
                       level_db: float = -24.0) -> np.ndarray:
    parts: list[np.ndarray] = []
    for i, (speaker, seconds) in enumerate(turns):
        voice = SPEAKERS[speaker]
        parts.append(synth_speech(seconds, voice["f0"], voice["formant_scale"], level_db=level_db, seed=seed + i))
        parts.append(silence(gap, seed=seed + 100 + i))
    return np.concatenate(parts)


def encode(samples: np.ndarray, path: str, codec: str = "aac") -> str:
    """Write samples to `path` (.m4a/.wav/.mp3) via ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        wav_path = handle.name
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    import wave

    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SR)
        wav.writeframes(pcm.tobytes())
    if path.endswith(".wav"):
        os.replace(wav_path, path)
        return path
    args = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", wav_path]
    if path.endswith(".m4a"):
        args += ["-c:a", "aac", "-b:a", "64k"]
    elif path.endswith(".mp3"):
        args += ["-c:a", "libmp3lame", "-b:a", "64k"]
    args.append(path)
    subprocess.run(args, check=True, capture_output=True)
    os.unlink(wav_path)
    return path


def audio_file(samples: np.ndarray, directory: str, name: str = "audio.m4a") -> str:
    return encode(samples, os.path.join(directory, name))
