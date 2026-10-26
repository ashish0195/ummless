"""User-facing copy for audio, attribution and evidence issues.

Copy never blames the user's communication for a technical problem, and never mentions accents.
"""

from __future__ import annotations

from ..schemas import Issue

_CATALOG: dict[str, tuple[str, str]] = {
    "file_unreadable": (
        "We couldn't open this recording",
        "The file may be damaged or in a format we can't read. Try exporting it again as M4A, MP3 or WAV.",
    ),
    "no_speech": (
        "We didn't hear any speech",
        "Check that the microphone wasn't covered or muted, then try again.",
    ),
    "too_short": (
        "There wasn't enough speech yet",
        "We need a little more of you talking to give useful feedback.",
    ),
    "too_quiet": (
        "Your voice was very quiet",
        "Hold the phone closer (about a forearm's length) or speak a little louder.",
    ),
    "noisy": (
        "There was a lot of background noise",
        "Try a quieter spot, or move closer to the phone so your voice stands out.",
    ),
    "clipping": (
        "The audio was distorted",
        "The microphone was overloaded. Hold the phone a little further away.",
    ),
    "overlapping_voices": (
        "Voices overlapped a lot",
        "We skipped parts where people talked over each other, because we can't tell who said what.",
    ),
    "background_voices": (
        "We heard another voice in the background",
        "We only used your voice. For the clearest results, practice somewhere you can talk alone.",
    ),
    "low_intelligibility": (
        "Some speech was hard to make out",
        "We left out parts we couldn't transcribe confidently — this is about the audio, not how you speak.",
    ),
    "multiple_speakers": (
        "We heard more than one person",
        "For your voice sample, record somewhere only you are talking.",
    ),
    "user_not_found": (
        "We couldn't find your voice",
        "None of the voices matched your voice sample confidently. Choose your voice or tell us you're not in it.",
    ),
    "speaker_uncertain": (
        "We're not sure which voice is yours",
        "Listen to the clips and pick the one that's you.",
    ),
    "too_little_user_speech": (
        "You didn't speak much in this recording",
        "We need more of your own speaking turns to give feedback.",
    ),
    "transcription_failed": (
        "We couldn't process this audio right now",
        "This was a problem on our side, not with how you spoke. Please try again.",
    ),
    "trimmed": (
        "We analyzed the first part of a long recording",
        "Recordings are analyzed up to the length limit; the rest was not used.",
    ),
}

BLOCKING = {"file_unreadable", "no_speech", "transcription_failed"}


def issue(code: str, severity: str | None = None, detail: str | None = None) -> Issue:
    title, default_detail = _CATALOG.get(code, ("Something affected this audio", "Please try again."))
    sev = severity or ("blocking" if code in BLOCKING else "warning")
    return Issue(code=code, title=title, detail=detail or default_detail, severity=sev)  # type: ignore[arg-type]
