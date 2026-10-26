"""Lightweight acoustic voiceprint used ONLY as a conflict check on speaker attribution.

MFCC mean/std plus median pitch. This is not speaker verification or identity authentication: it can
flag that a diarized "you" sounds unlike your voice reference (so we ask you to confirm), but it never
decides on its own. Thresholds: pilot calibration required.
"""

from __future__ import annotations

from typing import Literal

import numpy as np

SAMPLE_RATE = 16_000
N_FFT = 512
FRAME = 400  # 25 ms
HOP = 160  # 10 ms
N_MELS = 26
N_MFCC = 13

STRONG_MATCH = 0.60
WEAK_MATCH = 0.40


def _mel(f: np.ndarray | float) -> np.ndarray | float:
    return 2595.0 * np.log10(1.0 + np.asarray(f) / 700.0)


def _imel(m: np.ndarray | float) -> np.ndarray | float:
    return 700.0 * (10 ** (np.asarray(m) / 2595.0) - 1.0)


def _filterbank() -> np.ndarray:
    low, high = _mel(20.0), _mel(SAMPLE_RATE / 2)
    points = _imel(np.linspace(low, high, N_MELS + 2))
    bins = np.floor((N_FFT + 1) * points / SAMPLE_RATE).astype(int)
    bank = np.zeros((N_MELS, N_FFT // 2 + 1))
    for i in range(1, N_MELS + 1):
        left, center, right = bins[i - 1], bins[i], bins[i + 1]
        for k in range(left, center):
            if center > left:
                bank[i - 1, k] = (k - left) / (center - left)
        for k in range(center, right):
            if right > center:
                bank[i - 1, k] = (right - k) / (right - center)
    return bank


_BANK = _filterbank()


def _dct_matrix(n_out: int, n_in: int) -> np.ndarray:
    k = np.arange(n_out)[:, None]
    n = np.arange(n_in)[None, :]
    mat = np.cos(np.pi * k * (2 * n + 1) / (2 * n_in)) * np.sqrt(2.0 / n_in)
    mat[0] *= 1 / np.sqrt(2)
    return mat


_DCT = _dct_matrix(N_MFCC, N_MELS)


def mfcc(samples: np.ndarray) -> np.ndarray:
    """MFCC frames (n_frames × 13) for frames with meaningful energy."""
    if len(samples) < FRAME:
        return np.zeros((0, N_MFCC))
    emphasized = np.append(samples[0], samples[1:] - 0.97 * samples[:-1])
    n_frames = 1 + (len(emphasized) - FRAME) // HOP
    # cap work for very long inputs
    step = max(1, n_frames // 6000)
    idx = np.arange(0, n_frames, step)[:, None] * HOP + np.arange(FRAME)[None, :]
    frames = emphasized[idx] * np.hamming(FRAME)
    energy = np.sqrt(np.mean(frames**2, axis=1))
    threshold = max(np.percentile(energy, 40), 1e-4)
    frames = frames[energy >= threshold]
    if frames.shape[0] == 0:
        return np.zeros((0, N_MFCC))
    spectrum = np.abs(np.fft.rfft(frames, N_FFT)) ** 2 / N_FFT
    mel_energy = np.log(spectrum @ _BANK.T + 1e-10)
    return mel_energy @ _DCT.T


def pitch_track(samples: np.ndarray) -> np.ndarray:
    """F0 estimates (Hz) for voiced 40 ms frames, via normalized autocorrelation."""
    frame, hop = 640, 320
    if len(samples) < frame:
        return np.zeros(0)
    n_frames = 1 + (len(samples) - frame) // hop
    step = max(1, n_frames // 1500)
    min_lag, max_lag = int(SAMPLE_RATE / 400), int(SAMPLE_RATE / 70)
    window = np.hanning(frame)
    energies = []
    f0s: list[float] = []
    for i in range(0, n_frames, step):
        segment = samples[i * hop : i * hop + frame] * window
        energies.append(float(np.sqrt(np.mean(segment**2))))
    if not energies:
        return np.zeros(0)
    gate = max(np.percentile(energies, 40), 1e-4)
    for j, i in enumerate(range(0, n_frames, step)):
        if energies[j] < gate:
            continue
        segment = samples[i * hop : i * hop + frame] * window
        spec = np.fft.rfft(segment, 2 * frame)
        corr = np.fft.irfft(spec * np.conj(spec))[:frame]
        if corr[0] <= 0:
            continue
        corr = corr / corr[0]
        lag = min_lag + int(np.argmax(corr[min_lag:max_lag]))
        if corr[lag] > 0.45:
            f0s.append(SAMPLE_RATE / lag)
    return np.array(f0s)


def voiceprint(samples: np.ndarray) -> dict:
    coeffs = mfcc(samples)
    f0 = pitch_track(samples)
    if coeffs.shape[0] < 20:
        return {"valid": False, "seconds": round(len(samples) / SAMPLE_RATE, 2)}
    body = coeffs[:, 1:]  # drop c0 (loudness)
    return {
        "valid": True,
        "seconds": round(len(samples) / SAMPLE_RATE, 2),
        "mfcc_mean": [round(float(x), 4) for x in body.mean(axis=0)],
        "mfcc_std": [round(float(x), 4) for x in body.std(axis=0)],
        "f0_median": round(float(np.median(f0)), 1) if f0.size >= 5 else None,
        "f0_iqr": round(float(np.percentile(f0, 75) - np.percentile(f0, 25)), 1) if f0.size >= 5 else None,
    }


def similarity(a: dict, b: dict) -> float | None:
    """0–1 similarity between two voiceprints, or None if either is unusable."""
    if not a.get("valid") or not b.get("valid"):
        return None
    mean_a, mean_b = np.array(a["mfcc_mean"]), np.array(b["mfcc_mean"])
    spread = (np.array(a["mfcc_std"]) + np.array(b["mfcc_std"])) / 2 + 1e-3
    distance = float(np.sqrt(np.mean(((mean_a - mean_b) / spread) ** 2)))
    score = float(np.exp(-1.6 * distance))
    f0_a, f0_b = a.get("f0_median"), b.get("f0_median")
    if f0_a and f0_b:
        ratio = max(f0_a, f0_b) / min(f0_a, f0_b)
        if ratio > 1.15:
            score *= max(0.25, 1.0 - (ratio - 1.15) * 1.6)
    return round(min(1.0, max(0.0, score)), 3)


def strength(score: float | None) -> Literal["strong", "weak", "conflict"] | None:
    if score is None:
        return None
    if score >= STRONG_MATCH:
        return "strong"
    if score >= WEAK_MATCH:
        return "weak"
    return "conflict"
