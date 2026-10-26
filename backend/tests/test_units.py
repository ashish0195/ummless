"""Unit tests for the audio checks, evidence guards and speech statistics."""

from __future__ import annotations

import numpy as np

from app.audio import quality, voiceprint
from app.audio.speech_stats import aggregate_patterns, filler_counts, hedge_count
from app.domain.evidence import Unit, compute_stats, evidence_caps
from tests.audio_fixtures import silence, synth_speech


def test_quality_checks_classify_audio():
    normal = quality.analyze(synth_speech(15, seed=1), min_speech_seconds=3)
    assert normal.usable == "yes" and not normal.blocking
    quiet = quality.analyze(synth_speech(15, level_db=-60, seed=2), min_speech_seconds=3)
    assert quiet.usable == "no" and quiet.blocking[0] in ("too_quiet", "no_speech")
    noisy = quality.analyze(synth_speech(15, level_db=-30, noise_db=-33, seed=3), min_speech_seconds=3)
    assert noisy.usable == "no" and noisy.blocking == ["noisy"]
    empty = quality.analyze(silence(8), min_speech_seconds=3)
    assert empty.blocking == ["no_speech"]


def test_partly_usable_recording_keeps_good_windows():
    good = synth_speech(20, seed=4)
    bad = synth_speech(20, level_db=-60, seed=5)
    report = quality.analyze(np.concatenate([good, bad]), min_speech_seconds=5)
    assert report.usable in ("yes", "partly")
    assert report.usable_window_at(5.0) is True
    assert report.usable_window_at(30.0) is False


def test_voiceprint_is_a_conflict_signal():
    a1 = voiceprint.voiceprint(synth_speech(10, 115, 1.0, seed=10))
    a2 = voiceprint.voiceprint(synth_speech(10, 115, 1.0, seed=11))
    b = voiceprint.voiceprint(synth_speech(10, 215, 1.17, seed=12))
    same, different = voiceprint.similarity(a1, a2), voiceprint.similarity(a1, b)
    assert same is not None and different is not None and same > different + 0.2
    assert voiceprint.strength(different) == "conflict"


def test_overlap_ratio():
    assert quality.overlap_ratio([("A", 0, 10), ("B", 10, 20)]) == 0
    assert 0.3 < quality.overlap_ratio([("A", 0, 10), ("B", 5, 15)]) < 0.4


def _unit(uid, role, text, duration, activity=None, source="s1"):
    return Unit(uid=uid, role=role, speaker_name=role, text=text, source_type="conversation", source_id=source,
                activity_id=activity, duration=duration)


def test_evidence_caps_never_exceed_the_sample():
    long_answer = " ".join(["word"] * 80)
    units = [
        _unit("T0", "partner", "Tell me about something you love, and explain it like I'm new to it.", 4),
        _unit("T1", "user", long_answer, 30, "explain_interest"),
    ]
    caps = evidence_caps(compute_stats(units))
    assert caps["structure"].max_strength == "limited"
    assert caps["listening"].max_strength == "none"  # one exchange is not enough back-and-forth
    assert "back-and-forth" in caps["listening"].reason
    assert caps["storytelling"].max_strength == "limited" and caps["storytelling"].needs_model_opportunity
    tiny = evidence_caps(compute_stats([_unit("T1", "user", "Hi there friend", 2)]))
    assert all(cap.max_strength == "none" for cap in tiny.values())


def test_excluded_units_do_not_count():
    units = [_unit("T0", "partner", "Hello there, tell me about your weekend please, I'd love to hear.", 4),
             _unit("T1", "user", " ".join(["word"] * 100), 40)]
    units[1].excluded = True
    stats = compute_stats(units)
    assert stats.user_speech_seconds == 0 and stats.excluded_user_units == 1


def test_fillers_and_hedges_are_english_only():
    text = "Um, so I think it's, like, kind of good, you know? Like, maybe."
    assert filler_counts(text, "en")["um"] == 1
    assert filler_counts(text, "en")["like"] == 2
    assert hedge_count(text, "en") >= 3
    assert filler_counts(text, "fr") == {}
    patterns = aggregate_patterns([("Hola, creo que sí.", 30.0)], [0.5], "es")
    assert patterns.filler_per_minute is None and patterns.language_supported is False
