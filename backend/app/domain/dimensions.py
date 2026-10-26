"""The seven dimensions of the communication web, with 5-band rubrics.

Levels describe what was observed in a sample, never the person. There is deliberately no overall score.
"""

from __future__ import annotations

from dataclasses import dataclass

DIMENSION_IDS: tuple[str, ...] = (
    "clarity",
    "structure",
    "listening",
    "warmth",
    "persuasion",
    "concision",
    "storytelling",
)

LEVEL_LABELS: dict[int, str] = {
    1: "Emerging",
    2: "Developing",
    3: "Capable",
    4: "Strong",
    5: "Exceptional",
}


@dataclass(frozen=True)
class Dimension:
    id: str
    title: str
    description: str
    symbol: str  # SF Symbol name used by the app
    color_hex: str
    rubric: tuple[str, str, str, str, str]  # bands 1..5
    observe: str  # what an assessor should look for


DIMENSIONS: dict[str, Dimension] = {
    "clarity": Dimension(
        id="clarity",
        title="Clarity",
        description="Making your point easy to understand.",
        symbol="sun.max",
        color_hex="#2F9BFF",
        rubric=(
            "A listener would struggle to tell what the main point is; ideas are vague or jump around.",
            "The main point is there but buried or ambiguous; key terms or references are left unexplained.",
            "The main point is understandable; some vague language or unexplained jargon slows the listener down.",
            "The main point is clear early; language is concrete and terms are explained for this listener.",
            "Exceptionally clear: precise, concrete wording that anticipates where this listener could get lost.",
        ),
        observe="Is the main point identifiable? Is wording concrete? Are terms explained for this listener?",
    ),
    "structure": Dimension(
        id="structure",
        title="Structure",
        description="Organizing ideas so others can follow.",
        symbol="square.stack.3d.up",
        color_hex="#6366F1",
        rubric=(
            "Ideas arrive in no discernible order; the listener can't tell where the answer is going.",
            "Some order exists but there are detours, restarts or a missing ending.",
            "A recognizable shape (e.g. point → reasons, or chronological) with a few detours.",
            "A clear beginning, middle and end with signposting; detours are brief and relevant.",
            "Deliberate, elegant structure that fits the purpose and makes the content memorable.",
        ),
        observe="Is there a recognizable shape (point–reason–example, setup–turn–outcome)? Clear ending?",
    ),
    "listening": Dimension(
        id="listening",
        title="Listening",
        description="Showing you heard and understood the other person.",
        symbol="ear",
        color_hex="#10B3A3",
        rubric=(
            "Replies ignore what the other person said or move straight to the user's own agenda.",
            "Acknowledges the other person generically but responds to little of the specific content.",
            "Responds to the main thing said; occasional missed cues or premature advice.",
            "Picks up specifics, asks relevant follow-up questions, checks understanding before advising.",
            "Reflects both content and feeling accurately; builds on the other person's words naturally.",
        ),
        observe="Do replies reference specifics the other person said? Follow-up questions? Paraphrasing?",
    ),
    "warmth": Dimension(
        id="warmth",
        title="Warmth",
        description="Making the other person feel welcome and respected.",
        symbol="heart",
        color_hex="#FF8A3D",
        rubric=(
            "Comes across as dismissive or cold in this exchange.",
            "Polite but transactional; little interest shown in the other person.",
            "Friendly and respectful; some genuine interest or acknowledgement.",
            "Shows clear interest and empathy; acknowledges feelings; invites the other person in.",
            "Consistently generous and attuned; the other person would likely feel genuinely valued.",
        ),
        observe="Acknowledgement of feelings, interest in the other person, inclusive and kind language.",
    ),
    "persuasion": Dimension(
        id="persuasion",
        title="Persuasion",
        description="Making a case others want to agree with.",
        symbol="arrow.up.forward.circle",
        color_hex="#E64980",
        rubric=(
            "No clear ask or reason; objections are ignored or derail the case.",
            "An ask exists but reasons are generic or about the speaker, not the listener.",
            "A clear ask with at least one relevant reason; objections answered partially.",
            "Reasons fit the listener's interests; objections are acknowledged and answered with specifics.",
            "Compelling and adaptive: reframes around the listener's goals and turns objections into support.",
        ),
        observe="Clear ask? Reasons that matter to this listener? How objections are handled and adapted to.",
    ),
    "concision": Dimension(
        id="concision",
        title="Concision",
        description="Saying what matters without extra words.",
        symbol="scissors",
        color_hex="#7CB518",
        rubric=(
            "The point is lost in repetition, long preambles or tangents.",
            "Noticeable padding: restating, qualifying or circling before getting to the point.",
            "Mostly to the point with some repetition or hedging.",
            "Gets to the point quickly; little repetition; stops when done.",
            "Every sentence earns its place; economical without sounding curt.",
        ),
        observe="Time-to-point, repetition, padding and hedging. Shorter is NOT automatically better.",
    ),
    "storytelling": Dimension(
        id="storytelling",
        title="Storytelling",
        description="Bringing experiences to life for a listener.",
        symbol="text.book.closed",
        color_hex="#9B5DE5",
        rubric=(
            "Events are listed without a sense of story; hard to picture or follow.",
            "A sequence of events with little tension, detail or point.",
            "A recognizable story with a setup and outcome; some vivid detail.",
            "Engaging: a clear moment of change, concrete details and a reason it mattered.",
            "Gripping and purposeful: pacing, detail and meaning work together; the listener would retell it.",
        ),
        observe="Setup, turning point, concrete detail, consequence and meaning.",
    ),
}


def level_label(level: int | None) -> str | None:
    return LEVEL_LABELS.get(level) if level is not None else None


def rubric_text() -> str:
    """Rubric block for prompts."""
    lines: list[str] = []
    for dim in DIMENSIONS.values():
        lines.append(f"## {dim.title} ({dim.id}) — {dim.description}")
        lines.append(f"Look for: {dim.observe}")
        for index, band in enumerate(dim.rubric, start=1):
            lines.append(f"  {index} {LEVEL_LABELS[index]}: {band}")
    return "\n".join(lines)
