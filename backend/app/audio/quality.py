"""Audio usability checks: can we hear enough of the speech, clearly?

Energy-based measurements on 16 kHz mono audio, computed in 20 ms frames and 10 s windows so usable
sections of a partly bad recording survive. **All thresholds: pilot calibration required.** Audio
checks are deliberately lenient: transcription confidence is the stronger intelligibility signal, and
when in doubt we warn rather than reject. Unclear audio is never treated as poor communication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

SAMPLE_RATE = 16_000
FRAME = 320  # 20 ms
FRAME_SECONDS = FRAME / SAMPLE_RATE
WINDOW_SECONDS = 10.0

# --- thresholds (pilot calibration required) ---
VAD_MARGIN_DB = 9.0  # speech frames sit at least this far above the noise floor…
VAD_ABS_FLOOR_DB = -65.0  # …and above this absolute level
QUIET_WARN_DBFS = -45.0
QUIET_BLOCK_DBFS = -52.0
NOISY_WARN_SNR_DB = 10.0
NOISY_BLOCK_SNR_DB = 5.0
CLIP_SAMPLE = 0.995
CLIP_RATIO_WARN = 0.01
MIN_PAUSE_SECONDS = 0.25
MAX_INTERNAL_PAUSE_SECONDS = 3.0  # longer silences are turn breaks, not pauses
HANGOVER_FRAMES = 10  # bridge gaps shorter than 200 ms inside speech
MIN_RUN_FRAMES = 5  # ignore blips shorter than 100 ms


@dataclass
class WindowQuality:
    start: float
    end: float
    speech_seconds: float
    level_db: float | None
    usable: bool


@dataclass
class QualityReport:
    duration: float
    speech_seconds: float
    speech_level_db: float | None
    noise_floor_db: float
    snr_db: float | None
    clipping_ratio: float
    usable_seconds: float
    usable: Literal["yes", "partly", "no"]
    issues: list[str] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    windows: list[WindowQuality] = field(default_factory=list)
    speech_runs: list[tuple[float, float]] = field(default_factory=list)

    def usable_window_at(self, t: float) -> bool:
        for window in self.windows:
            if window.start <= t < window.end:
                return window.usable or window.speech_seconds < 0.5
        return True

    def as_dict(self) -> dict:
        return {
            "duration": round(self.duration, 2),
            "speech_seconds": round(self.speech_seconds, 2),
            "speech_level_db": None if self.speech_level_db is None else round(self.speech_level_db, 1),
            "noise_floor_db": round(self.noise_floor_db, 1),
            "snr_db": None if self.snr_db is None else round(self.snr_db, 1),
            "clipping_ratio": round(self.clipping_ratio, 4),
            "usable_seconds": round(self.usable_seconds, 2),
            "usable": self.usable,
            "issues": list(self.issues),
            "blocking": list(self.blocking),
        }


def frame_db(samples: np.ndarray) -> np.ndarray:
    """RMS level per 20 ms frame in dBFS, computed in chunks to bound memory."""
    n_frames = len(samples) // FRAME
    if n_frames == 0:
        return np.zeros(0, dtype=np.float32)
    out = np.empty(n_frames, dtype=np.float32)
    chunk = 3000  # frames per chunk (60 s)
    for start in range(0, n_frames, chunk):
        stop = min(n_frames, start + chunk)
        block = samples[start * FRAME : stop * FRAME].reshape(-1, FRAME).astype(np.float32)
        rms = np.sqrt(np.mean(block * block, axis=1) + 1e-12)
        out[start:stop] = 20.0 * np.log10(rms + 1e-10)
    return out


def _smooth_mask(mask: np.ndarray) -> np.ndarray:
    """Bridge short gaps and drop tiny blips."""
    if mask.size == 0:
        return mask
    result = mask.copy()
    # bridge gaps shorter than the hangover
    idx = np.flatnonzero(result)
    if idx.size:
        gaps = np.diff(idx)
        for pos in np.flatnonzero((gaps > 1) & (gaps <= HANGOVER_FRAMES)):
            result[idx[pos] : idx[pos + 1]] = True
    # remove short runs
    runs = runs_from_mask(result)
    for a, b in runs:
        if b - a < MIN_RUN_FRAMES:
            result[a:b] = False
    return result


def runs_from_mask(mask: np.ndarray) -> list[tuple[int, int]]:
    if mask.size == 0:
        return []
    padded = np.concatenate([[False], mask, [False]])
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(changes[i]), int(changes[i + 1])) for i in range(0, len(changes), 2)]


def speech_mask(levels: np.ndarray) -> tuple[np.ndarray, float]:
    if levels.size == 0:
        return np.zeros(0, dtype=bool), -100.0
    noise_floor = float(np.percentile(levels, 5))
    threshold = max(noise_floor + VAD_MARGIN_DB, VAD_ABS_FLOOR_DB)
    return _smooth_mask(levels > threshold), noise_floor


def pauses_between(runs: list[tuple[float, float]], start: float | None = None, end: float | None = None) -> list[float]:
    """Internal pauses (gaps between speech runs) within [start, end]."""
    selected = [(a, b) for a, b in runs if (start is None or b > start) and (end is None or a < end)]
    pauses: list[float] = []
    for (_, prev_end), (next_start, _) in zip(selected, selected[1:], strict=False):
        gap = next_start - prev_end
        if MIN_PAUSE_SECONDS <= gap <= MAX_INTERNAL_PAUSE_SECONDS:
            pauses.append(round(gap, 3))
    return pauses


def analyze(samples: np.ndarray, *, min_speech_seconds: float) -> QualityReport:
    duration = len(samples) / SAMPLE_RATE
    levels = frame_db(samples)
    mask, noise_floor = speech_mask(levels)
    speech_frames = levels[mask] if levels.size else levels
    speech_seconds = float(mask.sum()) * FRAME_SECONDS
    speech_level = float(np.median(speech_frames)) if speech_frames.size else None
    snr = (float(np.percentile(speech_frames, 90)) - noise_floor) if speech_frames.size else None
    clipping_ratio = float(np.mean(np.abs(samples) >= CLIP_SAMPLE)) if samples.size else 0.0

    frame_runs = runs_from_mask(mask)
    speech_runs = [(round(a * FRAME_SECONDS, 3), round(b * FRAME_SECONDS, 3)) for a, b in frame_runs]

    # 10-second windows
    windows: list[WindowQuality] = []
    frames_per_window = int(WINDOW_SECONDS / FRAME_SECONDS)
    for w_start in range(0, max(1, levels.size), frames_per_window):
        w_end = min(levels.size, w_start + frames_per_window)
        w_mask = mask[w_start:w_end]
        w_levels = levels[w_start:w_end][w_mask]
        w_speech = float(w_mask.sum()) * FRAME_SECONDS
        w_level = float(np.median(w_levels)) if w_levels.size else None
        sample_a, sample_b = w_start * FRAME, w_end * FRAME
        w_clip = float(np.mean(np.abs(samples[sample_a:sample_b]) >= CLIP_SAMPLE)) if sample_b > sample_a else 0.0
        usable = bool(
            w_speech >= 0.5
            and w_level is not None
            and w_level >= QUIET_BLOCK_DBFS
            and (w_level - noise_floor) >= NOISY_BLOCK_SNR_DB
            and w_clip <= CLIP_RATIO_WARN * 5
        )
        windows.append(
            WindowQuality(
                start=round(w_start * FRAME_SECONDS, 2),
                end=round(w_end * FRAME_SECONDS, 2),
                speech_seconds=round(w_speech, 2),
                level_db=None if w_level is None else round(w_level, 1),
                usable=usable,
            )
        )
    usable_seconds = sum(w.speech_seconds for w in windows if w.usable)

    issues: list[str] = []
    blocking: list[str] = []
    quiet_windows = any(w.level_db is not None and w.level_db < QUIET_BLOCK_DBFS for w in windows)
    if speech_seconds < 0.5:
        # Loud, steady noise can hide speech from the energy VAD: say so rather than "no speech".
        blocking.append("noisy" if noise_floor > -45.0 else "no_speech")
    else:
        # Global measurements are warnings; they only block when too little usable speech is left
        # (usable sections of a partly bad recording must survive).
        if (speech_level is not None and speech_level < QUIET_WARN_DBFS) or quiet_windows:
            issues.append("too_quiet")
        if snr is not None and snr < NOISY_WARN_SNR_DB:
            issues.append("noisy")
        if clipping_ratio > CLIP_RATIO_WARN:
            issues.append("clipping")
        if usable_seconds < min_speech_seconds:
            if speech_seconds < min_speech_seconds:
                blocking.append("too_short")
            elif quiet_windows or (speech_level is not None and speech_level < QUIET_BLOCK_DBFS):
                blocking.append("too_quiet")
            elif snr is not None and snr < NOISY_BLOCK_SNR_DB or "noisy" in issues:
                blocking.append("noisy")
            else:
                blocking.append("too_short")
            issues = [code for code in issues if code not in blocking]

    if blocking:
        usable_state: Literal["yes", "partly", "no"] = "no"
    elif usable_seconds < 0.8 * speech_seconds or issues:
        usable_state = "partly"
    else:
        usable_state = "yes"

    return QualityReport(
        duration=duration,
        speech_seconds=speech_seconds,
        speech_level_db=speech_level,
        noise_floor_db=noise_floor,
        snr_db=snr,
        clipping_ratio=clipping_ratio,
        usable_seconds=usable_seconds,
        usable=usable_state,
        issues=issues,
        blocking=blocking,
        windows=windows,
        speech_runs=speech_runs,
    )


def overlap_ratio(segments: list[tuple[str, float, float]]) -> float:
    """Share of speech time where two or more different speakers overlap."""
    events: list[tuple[float, int, str]] = []
    for speaker, start, end in segments:
        if end > start:
            events.append((start, 1, speaker))
            events.append((end, -1, speaker))
    if not events:
        return 0.0
    events.sort(key=lambda e: (e[0], e[1]))
    active: dict[str, int] = {}
    last_t = events[0][0]
    overlap = 0.0
    speech = 0.0
    for t, delta, speaker in events:
        n_active = sum(1 for v in active.values() if v > 0)
        span = t - last_t
        if n_active >= 1:
            speech += span
        if n_active >= 2:
            overlap += span
        active[speaker] = active.get(speaker, 0) + delta
        last_t = t
    return overlap / speech if speech > 0 else 0.0
