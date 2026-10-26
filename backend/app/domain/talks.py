"""Talks for "steal their style" shadowing.

Only public-domain speeches (US government works / 19th-century texts) and original exemplar scripts
written for Comlogue. `[pause]` marks a deliberate beat the user practices holding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PAUSE_MARK = "[pause]"


@dataclass(frozen=True)
class TalkDef:
    id: str
    title: str
    speaker: str
    source_note: str
    year: int | None
    duration_label: str
    wpm: float
    avg_pause_seconds: float
    tags: tuple[str, ...]
    technique: str
    breakdown: tuple[str, ...]
    lines: tuple[str, ...]
    tts_voice: str
    tts_instructions: str


def display_text(line: str) -> str:
    text = line.replace(PAUSE_MARK, " ")
    return re.sub(r"\s+", " ", text).strip()


def pause_count(line: str) -> int:
    return line.count(PAUSE_MARK)


def tts_text(line: str) -> str:
    """Pause markers become ellipses, which TTS models render as audible beats."""
    text = line.replace(PAUSE_MARK, "…")
    return re.sub(r"\s+", " ", text).strip()


def avg_sentence_words(talk: TalkDef) -> float:
    text = " ".join(display_text(line) for line in talk.lines)
    sentences = [s for s in re.split(r"[.!?]+\s*", text) if s.strip()]
    words = len(re.findall(r"[\w']+", text))
    return round(words / max(1, len(sentences)), 1)


TALKS: tuple[TalkDef, ...] = (
    TalkDef(
        id="decision_meeting",
        title="Run a decision meeting in 15 minutes",
        speaker="Comlogue exemplar · engineering leader",
        source_note="Original script written for Comlogue.",
        year=None,
        duration_label="1 min",
        wpm=138,
        avg_pause_seconds=1.1,
        tags=("meetings", "leadership", "concision"),
        technique="Decision-first framing",
        breakdown=(
            "Opens with the decision, the owner and the ask in nine words.",
            "Each option gets the same two-beat shape, so they're easy to compare.",
            "Names what would change the speaker's mind — which invites real disagreement.",
            "Pauses separate ideas so the room can keep up and respond.",
        ),
        lines=(
            "Here's the decision. [pause] Here's who owns it. [pause] Disagree now, or commit.",
            "We have fifteen minutes, [pause] and one question: [pause] do we ship the new onboarding on Monday?",
            "Option one: ship Monday. [pause] We learn faster, [pause] and support is ready.",
            "Option two: wait two weeks. [pause] We fix the edge cases, [pause] and lose two weeks of data.",
            "My recommendation is to ship Monday, [pause] behind a flag, [pause] for ten percent of new users.",
            "Two reasons. [pause] The risky cases are rare. [pause] And the flag lets us roll back in minutes.",
            "What would change my mind? [pause] Evidence that the rare cases aren't rare.",
            "Lin, you know the data best. [pause] What am I missing?",
            "Okay. [pause] Here's where we landed: [pause] we ship Monday, behind the flag, at ten percent.",
            "Priya owns the rollout. [pause] Ravi owns the rollback plan.",
            "If you disagree, [pause] say it now. [pause] Otherwise, we commit.",
            "Thanks, everyone. [pause] That's the decision.",
        ),
        tts_voice="cedar",
        tts_instructions=(
            "Voice: calm, confident engineering leader. Pace: measured, about 135 words per minute. Hold a full "
            "one-second pause at every ellipsis. Warm but decisive."
        ),
    ),
    TalkDef(
        id="project_update",
        title="The 60-second project update",
        speaker="Comlogue exemplar · program manager",
        source_note="Original script written for Comlogue.",
        year=None,
        duration_label="1 min",
        wpm=150,
        avg_pause_seconds=0.9,
        tags=("meetings", "structure"),
        technique="Headline, status, risk, ask",
        breakdown=(
            "The first sentence is the headline — a listener could stop there and know the state.",
            "Signposts ('Where we are', 'The risk', 'What I need') make the structure audible.",
            "One ask, stated plainly, near the end.",
        ),
        lines=(
            "Quick update on the billing migration. [pause] Headline: we're on track, with one risk.",
            "Where we are: [pause] eighty percent of accounts have moved, [pause] with zero failed payments.",
            "The risk: [pause] the last twenty percent are our largest customers, [pause] and their invoices are custom.",
            "What we're doing about it: [pause] we've paired each one with an account manager, [pause] and we'll "
            "move them one by one.",
            "What I need from you: [pause] a yes on extending the freeze by one week.",
            "If we get that, [pause] we finish on the twelfth. [pause] Questions?",
        ),
        tts_voice="marin",
        tts_instructions=(
            "Voice: clear, upbeat professional. Pace: brisk but unhurried, about 150 words per minute. Short "
            "pause at each ellipsis. Emphasize the signpost words."
        ),
    ),
    TalkDef(
        id="toast",
        title="A toast that lands",
        speaker="Comlogue exemplar · a friend at a farewell",
        source_note="Original script written for Comlogue.",
        year=None,
        duration_label="45 sec",
        wpm=140,
        avg_pause_seconds=1.0,
        tags=("storytelling", "social"),
        technique="One story, one trait, one wish",
        breakdown=(
            "Starts inside a specific moment instead of with background.",
            "The story proves a single trait, so the meaning lands without explanation.",
            "The final line turns the story into a wish for the future.",
        ),
        lines=(
            "I met Jordan on the worst first day of work in history.",
            "The fire alarm went off at nine. [pause] We stood in the rain for an hour, [pause] and Jordan spent "
            "it learning everyone's name.",
            "By the time we got back inside, [pause] Jordan knew half the office. [pause] I knew where the exit was.",
            "That's Jordan. [pause] Wherever things go wrong, [pause] Jordan makes it a place people want to be.",
            "So tonight, [pause] as you start this next chapter, [pause] we know one thing for sure:",
            "whoever you meet there [pause] is about to have a much better first day. [pause] To Jordan!",
        ),
        tts_voice="coral",
        tts_instructions=(
            "Voice: warm friend giving a toast. Tone: affectionate with a smile. Pace: relaxed. Pause at each "
            "ellipsis and let the funny line breathe."
        ),
    ),
    TalkDef(
        id="gettysburg",
        title="Gettysburg Address",
        speaker="Abraham Lincoln",
        source_note="1863. Public domain (Bliss copy).",
        year=1863,
        duration_label="2 min",
        wpm=110,
        avg_pause_seconds=1.3,
        tags=("public speaking", "rhetoric"),
        technique="Rule of three and parallel structure",
        breakdown=(
            "272 words, about two minutes. Brevity is the point.",
            "Triads carry the rhythm: 'dedicate… consecrate… hallow' and 'of the people, by the people, for "
            "the people'.",
            "Moves from past ('four score') to present ('we are met') to future ('a new birth of freedom').",
            "Short sentences give weight: 'It is altogether fitting and proper that we should do this.'",
        ),
        lines=(
            "Four score and seven years ago [pause] our fathers brought forth on this continent, a new nation, "
            "[pause] conceived in Liberty, [pause] and dedicated to the proposition that all men are created equal.",
            "Now we are engaged in a great civil war, [pause] testing whether that nation, or any nation so "
            "conceived and so dedicated, [pause] can long endure.",
            "We are met on a great battle-field of that war. [pause] We have come to dedicate a portion of that "
            "field, as a final resting place for those who here gave their lives that that nation might live.",
            "It is altogether fitting and proper that we should do this.",
            "But, in a larger sense, [pause] we can not dedicate — [pause] we can not consecrate — [pause] we can "
            "not hallow — [pause] this ground.",
            "The brave men, living and dead, who struggled here, have consecrated it, [pause] far above our poor "
            "power to add or detract.",
            "The world will little note, nor long remember what we say here, [pause] but it can never forget what "
            "they did here.",
            "It is for us the living, rather, to be dedicated here to the unfinished work which they who fought "
            "here have thus far so nobly advanced.",
            "It is rather for us to be here dedicated to the great task remaining before us — [pause] that from "
            "these honored dead we take increased devotion to that cause for which they gave the last full measure "
            "of devotion —",
            "that we here highly resolve that these dead shall not have died in vain — [pause] that this nation, "
            "under God, shall have a new birth of freedom —",
            "and that government of the people, [pause] by the people, [pause] for the people, [pause] shall not "
            "perish from the earth.",
        ),
        tts_voice="cedar",
        tts_instructions=(
            "Voice: solemn, dignified orator. Pace: slow, about 110 words per minute. Hold a long pause at each "
            "ellipsis. Gravity without melodrama."
        ),
    ),
    TalkDef(
        id="jfk_inaugural",
        title="Inaugural Address (excerpt)",
        speaker="John F. Kennedy",
        source_note="1961. US government work, public domain.",
        year=1961,
        duration_label="1.5 min",
        wpm=112,
        avg_pause_seconds=1.5,
        tags=("public speaking", "persuasion"),
        technique="Antithesis (reversal)",
        breakdown=(
            "Antithesis flips a phrase to create a memorable contrast: 'ask not what… ask what…'.",
            "Long pauses let big lines land before moving on.",
            "Lists of parallel verbs build momentum: 'pay any price, bear any burden'.",
        ),
        lines=(
            "We observe today not a victory of party, [pause] but a celebration of freedom.",
            "Let the word go forth from this time and place, [pause] to friend and foe alike, [pause] that the "
            "torch has been passed to a new generation of Americans.",
            "Let every nation know, whether it wishes us well or ill, [pause] that we shall pay any price, bear any "
            "burden, meet any hardship, support any friend, oppose any foe, [pause] to assure the survival and the "
            "success of liberty.",
            "And so, my fellow Americans: [pause] ask not what your country can do for you — [pause] ask what you "
            "can do for your country.",
            "My fellow citizens of the world: [pause] ask not what America will do for you, [pause] but what "
            "together we can do for the freedom of man.",
        ),
        tts_voice="echo",
        tts_instructions=(
            "Voice: resonant, confident orator. Pace: slow and deliberate. Long pause at each ellipsis; land the "
            "contrast in each 'ask not' line."
        ),
    ),
    TalkDef(
        id="fdr_infamy",
        title="Address to Congress (excerpt)",
        speaker="Franklin D. Roosevelt",
        source_note="December 8, 1941. US government work, public domain.",
        year=1941,
        duration_label="1 min",
        wpm=105,
        avg_pause_seconds=1.4,
        tags=("public speaking", "clarity"),
        technique="Plain words, heavy pauses",
        breakdown=(
            "Opens with the date and the fact — no warm-up.",
            "Very short sentences ('Hostilities exist.') carry the most weight.",
            "Measured pace signals control in a crisis.",
        ),
        lines=(
            "Yesterday, December 7th, 1941 — [pause] a date which will live in infamy — [pause] the United States "
            "of America was suddenly and deliberately attacked by naval and air forces of the Empire of Japan.",
            "No matter how long it may take us to overcome this premeditated invasion, [pause] the American people "
            "in their righteous might will win through to absolute victory.",
            "Hostilities exist. [pause] There is no blinking at the fact that our people, our territory, and our "
            "interests are in grave danger.",
            "With confidence in our armed forces — [pause] with the unbounding determination of our people — "
            "[pause] we will gain the inevitable triumph — [pause] so help us God.",
        ),
        tts_voice="onyx",
        tts_instructions=(
            "Voice: grave, steady statesman. Pace: slow, about 105 words per minute. Long pauses at each ellipsis. "
            "Calm authority."
        ),
    ),
    TalkDef(
        id="sojourner_truth",
        title="Ain't I a Woman? (excerpt)",
        speaker="Sojourner Truth",
        source_note=(
            "As recorded by Frances Dana Gage (1863); public domain. Historians consider Marius Robinson's 1851 "
            "report closer to what Truth actually said."
        ),
        year=1851,
        duration_label="1 min",
        wpm=120,
        avg_pause_seconds=1.2,
        tags=("persuasion", "storytelling"),
        technique="The refrain",
        breakdown=(
            "A repeated question ('And ain't I a woman?') turns each example into evidence.",
            "Concrete, physical details ('Look at my arm!') make the argument impossible to wave away.",
            "Each example builds on the last, so the refrain gets heavier every time.",
        ),
        lines=(
            "That man over there says that women need to be helped into carriages, and lifted over ditches, "
            "[pause] and to have the best place everywhere.",
            "Nobody ever helps me into carriages, or over mud-puddles, or gives me any best place! [pause] And "
            "ain't I a woman?",
            "Look at me! [pause] Look at my arm! [pause] I have ploughed and planted, and gathered into barns, and "
            "no man could head me! [pause] And ain't I a woman?",
            "I could work as much and eat as much as a man — when I could get it — and bear the lash as well! "
            "[pause] And ain't I a woman?",
        ),
        tts_voice="sage",
        tts_instructions=(
            "Voice: powerful, grounded speaker. Pace: deliberate. Build intensity on each refrain and pause before "
            "'And ain't I a woman?'"
        ),
    ),
)

TALKS_BY_ID: dict[str, TalkDef] = {talk.id: talk for talk in TALKS}
