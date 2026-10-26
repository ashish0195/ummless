"""Compute a conversational-twin reference profile from a licensed or public-domain speech.

The conversational twin compares a few measurable speaking habits (pace, pausing, sentence length,
questions, qualifiers). This script measures the same habits for a reference speaker so they can be added
to `app/domain/archetypes.py`. Only use recordings you have the rights to (e.g. US presidential speeches,
which are US government works) and get legal sign-off before naming real people in the product.

Usage (from backend/):
    python scripts/build_twin_profile.py --audio speech.mp3 --transcript speech.txt --name "Reference name" \
        --blurb "One-line description of the style"

The transcript should contain only the reference speaker's words.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audio import ffmpeg, quality  # noqa: E402
from app.audio.speech_stats import style_vector  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--blurb", required=True)
    args = parser.parse_args()

    text = Path(args.transcript).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "speech.wav")
        ffmpeg.decode_to_wav16k(args.audio, wav)
        samples = ffmpeg.read_wav(wav)
    report = quality.analyze(samples, min_speech_seconds=10)
    runs = report.speech_runs
    span = (runs[-1][1] - runs[0][0]) if runs else report.duration
    vector = style_vector([(text, span)], quality.pauses_between(runs))
    if vector is None:
        raise SystemExit("Not enough speech to build a profile (need at least 30 seconds).")
    print("Add this to TWIN_REFERENCES in app/domain/archetypes.py:\n")
    print(
        f'    TwinReference("{args.name}", "{args.blurb}", {vector["wpm"]:.0f}, {vector["avg_pause_seconds"]:.2f}, '
        f'{vector["sentence_words"]:.0f}, {vector["questions_per_min"]:.2f}, {vector["hedges_per_min"]:.2f}),'
    )


if __name__ == "__main__":
    main()
