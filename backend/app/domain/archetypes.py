"""Style archetypes and conversational-twin reference profiles.

Twin references are *illustrative* communicator profiles, not real people. Naming living celebrities
implies endorsement and raises right-of-publicity issues; real public-domain or licensed reference
speakers can be added with `scripts/build_twin_profile.py` once legal approves the list.
"""

from __future__ import annotations

from dataclasses import dataclass

STYLE_ARCHETYPES: dict[str, str] = {
    "The Explainer": "Breaks ideas into steps and checks the listener is following.",
    "The Connector": "Builds rapport quickly; asks about people and shares in return.",
    "The Storyteller": "Makes points through vivid moments and examples.",
    "The Strategist": "Leads with the big picture, then the reasons and trade-offs.",
    "The Diplomat": "Acknowledges other views and looks for common ground.",
    "The Spark": "High energy and enthusiasm that pulls others in.",
    "The Straight Shooter": "Direct and economical; says the point and stops.",
}

TWIN_DISCLAIMER = (
    "Reference styles are illustrative profiles, not real people. Matches compare a few measurable speaking "
    "habits in your sampled conversations — sounding alike isn't the same as communicating alike."
)


@dataclass(frozen=True)
class TwinReference:
    name: str
    blurb: str
    wpm: float  # pace
    avg_pause_seconds: float  # pausing
    sentence_words: float  # sentence length
    questions_per_min: float  # curiosity
    hedges_per_min: float  # certainty


TWIN_REFERENCES: tuple[TwinReference, ...] = (
    TwinReference("The Measured Statesman", "Slow, weighty sentences with long, deliberate pauses.", 120, 1.4, 18, 0.2, 0.2),
    TwinReference("The Energetic Keynoter", "Fast, punchy lines that keep a big room awake.", 168, 0.6, 11, 0.8, 0.3),
    TwinReference("The Late-Night Storyteller", "Easy rhythm, vivid detail and a playful pause before the punchline.", 150, 0.9, 14, 0.4, 0.6),
    TwinReference("The Socratic Coach", "Leads with questions and lets you find the answer.", 135, 1.0, 10, 2.5, 0.4),
    TwinReference("The Crisp Executive", "Short sentences, few qualifiers, decision first.", 145, 0.8, 9, 0.5, 0.1),
    TwinReference("The Warm Host", "Curious and inclusive; lots of questions and gentle qualifiers.", 155, 0.7, 12, 1.5, 0.8),
)

# aspect -> (title, attribute, scale used to normalize distance, formatter)
TWIN_ASPECTS: dict[str, tuple[str, str, float]] = {
    "pace": ("Pace", "wpm", 40.0),
    "pausing": ("Pausing", "avg_pause_seconds", 0.8),
    "sentence_length": ("Sentence length", "sentence_words", 8.0),
    "curiosity": ("Questions", "questions_per_min", 1.5),
    "certainty": ("Qualifiers", "hedges_per_min", 0.8),
}


def format_aspect(aspect: str, value: float) -> str:
    if aspect == "pace":
        return f"{round(value)} wpm"
    if aspect == "pausing":
        return f"{value:.1f}s pauses"
    if aspect == "sentence_length":
        return f"{round(value)} words/sentence"
    if aspect == "curiosity":
        return f"{value:.1f} questions/min"
    if aspect == "certainty":
        return f"{value:.1f} qualifiers/min"
    return f"{value:.1f}"
