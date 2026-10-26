"""Versioned consent texts. Changing the wording requires bumping the version string."""

from __future__ import annotations

from ..schemas import Consents, ConsentText

ANALYSIS_VERSION = "analysis-2026-10"
VOICE_REFERENCE_VERSION = "voice-2026-10"
RECORDING_VERSION = "recording-2026-10"

ANALYSIS = ConsentText(
    version=ANALYSIS_VERSION,
    title="How Comlogue uses your voice",
    body="To give you feedback, Comlogue records what you say during practice and analyzes it with AI.",
    bullets=[
        "Your audio is transcribed and analyzed by our AI provider (OpenAI) to produce your feedback. "
        "OpenAI does not use it to train models.",
        "We only assess what you say and how you structure it — never your accent or pronunciation.",
        "If audio is unclear, we tell you and skip it. Unclear audio never lowers your results.",
        "Recordings and results stay in your account until you delete them. You can delete any recording, "
        "or everything, at any time in Settings.",
    ],
)

VOICE_REFERENCE = ConsentText(
    version=VOICE_REFERENCE_VERSION,
    title="Save a voice reference?",
    body="We'll keep a short sample of your voice so we can find your speaking turns in recordings you add.",
    bullets=[
        "Used only to tell which voice is yours in your own recordings — not to identify you anywhere else, "
        "and not as a password.",
        "We store an 8-second clip and a few voice measurements. During analysis the clip is sent to our AI "
        "provider (OpenAI) as a reference for that recording only.",
        "The setup recording is never scored.",
        "Replace or delete it anytime in Settings. We also delete it after 18 months without use.",
        "Prefer not to? You can pick your voice manually in each recording instead.",
    ],
)

RECORDING = ConsentText(
    version=RECORDING_VERSION,
    title="Before you record a conversation",
    body="Everyone in the conversation must know it's being recorded and agree to it.",
    bullets=[
        "We analyze the recording to give you feedback. Only your own speaking turns are assessed.",
        "Other people's voices are used only as context. They are never added to your profile.",
        "You can delete the recording and everything derived from it at any time.",
    ],
)

ALL = Consents(analysis=ANALYSIS, voice_reference=VOICE_REFERENCE, recording=RECORDING)
