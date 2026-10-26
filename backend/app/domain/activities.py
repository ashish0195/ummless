"""The five guided-assessment activities (from the spec table) and the partner character, Maya.

Each activity is a short, low-stakes conversation that creates a *specific opportunity* for certain
dimensions. The partner always speaks first. After each user turn the partner performs the next step
of the activity's follow-up policy; the last step is a brief, natural close.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAYA = {
    "name": "Maya",
    "role": "Someone you've just met",
    "voice": "marin",
    "symbol": "person.wave.2",
    "color_hex": "#FF8A3D",
}

MAYA_CHARACTER = (
    "You are Maya, 31, a pediatric nurse who moved to the city eight months ago. You recently got into "
    "bouldering at a gym near your flat, you're slowly learning to cook Sri Lankan food from your grandmother's "
    "recipes over video calls, and you have a slightly chaotic rescue dog called Biscuit. You're warm, curious, "
    "a little playful, and you listen properly. You speak casually, like a real person at a friend's gathering — "
    "short sentences, contractions, no lists, no lecturing."
)

MAYA_TTS_INSTRUCTIONS = (
    "Voice: warm, relaxed and curious, early thirties. Tone: friendly and natural, like chatting at a friend's "
    "gathering. Pace: easy conversational pace with small natural pauses. Never sound like an announcer."
)


@dataclass(frozen=True)
class Step:
    key: str
    instruction: str  # what the partner should do now (fed to the conversation model)
    fallback: str  # deterministic line used by the demo provider or if the model fails


@dataclass(frozen=True)
class Activity:
    id: str
    title: str
    prompt: str  # the partner's opening line (from the spec)
    duration_label: str
    suggested_seconds: int
    minutes: int
    dimensions: tuple[str, ...]
    context: str  # one-line framing shown to the user
    tips: tuple[str, ...]
    steps: tuple[Step, ...]  # follow-ups after user turns 1..n-1; the last step closes the activity
    max_user_turns: int
    policy_notes: str = ""
    demo_answers: tuple[str, ...] = field(default_factory=tuple)

    @property
    def follow_up_steps(self) -> tuple[Step, ...]:
        return self.steps


CLOSE_INSTRUCTION = (
    "Close this part of the conversation in one short, warm sentence that responds to what they just said. "
    "Do not ask another question."
)

ACTIVITIES: dict[str, Activity] = {
    "meet_someone_new": Activity(
        id="meet_someone_new",
        title="Meet someone new",
        prompt="We've just met at a friend's gathering. What's something you've been spending time on lately?",
        duration_label="1–2 min",
        suggested_seconds=60,
        minutes=2,
        dimensions=("clarity", "warmth", "listening", "concision"),
        context="You've just met Maya at a friend's gathering. Chat the way you normally would.",
        tips=("There's no right answer — talk like you would at a party.", "Ask Maya something back if you like."),
        steps=(
            Step(
                "ask_detail",
                "Ask ONE curious follow-up question about a specific detail they mentioned (quote or reference "
                "it). Keep it to one or two short sentences.",
                "Oh nice — what got you into that in the first place?",
            ),
            Step(
                "share_self",
                "React briefly to their answer, then share a little about yourself (Maya) that connects to what "
                "they said — one or two sentences — so they have something to respond to. End by leaving space "
                "for them to respond (no direct question needed).",
                "That's lovely. I've been getting into bouldering lately — I'm terrible at it, but my rescue "
                "dog Biscuit thinks the gym is the best place on earth.",
            ),
            Step("close", CLOSE_INSTRUCTION, "Ha, I love that. It's really nice to meet you."),
        ),
        max_user_turns=3,
        policy_notes="Listening and warmth evidence comes from how they respond to Maya's sharing.",
        demo_answers=(
            "Lately I've been spending a lot of time learning to bake sourdough. I started during a long "
            "winter and now I'm kind of obsessed, I bake every weekend and give most of it away to neighbors.",
            "Honestly it started because a friend gave me some starter, and I didn't want to kill it, so I "
            "just kept feeding it and, um, one thing led to another.",
            "Bouldering, wow. How long have you been doing that? And Biscuit sounds like a great climbing "
            "coach. Does he actually come inside the gym?",
        ),
    ),
    "explain_interest": Activity(
        id="explain_interest",
        title="Explain an interest",
        prompt="Pick something you know or enjoy. Explain it to me as someone completely new to it.",
        duration_label="2 min",
        suggested_seconds=90,
        minutes=2,
        dimensions=("clarity", "structure", "concision"),
        context="Maya knows nothing about your topic. Help her understand it.",
        tips=("Pick something you genuinely know well.", "Imagine Maya has never heard of it."),
        steps=(
            Step(
                "clarify",
                "Ask ONE plausible clarification question a genuine newcomer would ask about something they "
                "said that might be confusing (name the specific term or step).",
                "Wait, sorry — what does that actually mean in practice?",
            ),
            Step(
                "main_thing",
                "Briefly acknowledge their answer, then ask exactly: \"What's the main thing you'd want me to "
                "remember?\"",
                "Got it, thanks. What's the main thing you'd want me to remember?",
            ),
            Step("close", CLOSE_INSTRUCTION, "That makes sense — I think I'd actually remember that."),
        ),
        max_user_turns=3,
        demo_answers=(
            "Sure, so I play chess. The basic idea is two players each control an army of sixteen pieces, and "
            "the goal is to trap the other player's king so it can't escape. Each piece moves differently, "
            "and the strategy comes from controlling the center of the board early on.",
            "Controlling the center just means putting your pieces on the middle squares, because from there "
            "they can reach more of the board, so you have more options than your opponent.",
            "The main thing is: every move should give you more options and your opponent fewer.",
        ),
    ),
    "respond_to_someone": Activity(
        id="respond_to_someone",
        title="Respond to someone",
        prompt=(
            "I joined a new team a month ago. Everyone's friendly, but I still feel outside the group. "
            "Yesterday I had an idea and didn't say anything."
        ),
        duration_label="2–3 min",
        suggested_seconds=90,
        minutes=3,
        dimensions=("listening", "warmth"),
        context="Maya is opening up about something that's bothering her. Respond the way you would to a friend.",
        tips=("Respond to what Maya actually says.", "There's no need to fix it unless that's what she wants."),
        steps=(
            Step(
                "respond",
                "Respond to what they actually said, as Maya. If they jumped straight to advice or solutions, "
                "gently clarify: \"I think I mostly wanted to talk it through first.\" If they asked a question "
                "or reflected your feelings, answer honestly and share a bit more about how it felt yesterday "
                "(you worried the idea was obvious and that you'd look silly).",
                "I think I mostly wanted to talk it through first. It's just — I kept thinking the idea was "
                "probably obvious and I'd look silly.",
            ),
            Step(
                "open_up",
                "React to their reply as Maya. If they have listened well, say what helped. If they are still "
                "rushing to advice, say you appreciate it but you're not sure yet. One or two sentences.",
                "Yeah… hearing it out loud, maybe it isn't as obvious as I thought.",
            ),
            Step("close", CLOSE_INSTRUCTION, "Thanks for listening. That actually helped."),
        ),
        max_user_turns=3,
        policy_notes="Responsiveness to the clarification is key listening evidence.",
        demo_answers=(
            "Oh, that sounds hard. A month isn't long though. You should just bring the idea up in the next "
            "meeting, honestly, people love new ideas.",
            "That makes sense. So it sounds like it's less about the idea and more about feeling like you "
            "belong yet. What was the idea, if you don't mind me asking?",
            "I don't think it sounds silly at all. It sounds like you care about getting it right.",
        ),
    ),
    "make_a_case": Activity(
        id="make_a_case",
        title="Make a case",
        prompt="Suggest an activity we could do together this weekend and try to get me interested.",
        duration_label="2–3 min",
        suggested_seconds=75,
        minutes=3,
        dimensions=("persuasion", "listening", "structure", "concision"),
        context="Convince Maya to join you for something this weekend.",
        tips=("Think about what Maya might enjoy.", "Expect a reasonable objection — adapt to it."),
        steps=(
            Step(
                "objection",
                "Show mild interest, then raise ONE reasonable objection about time, cost, or preference that "
                "fits what they proposed (e.g. you're on night shifts this weekend, money is tight this month, "
                "or you're not a fan of crowds). Leave room for them to adapt.",
                "Hmm, it sounds fun, but I'm on a night shift Saturday, so I'll be wrecked most of the day.",
            ),
            Step(
                "close",
                "React honestly to how they adapted, then wrap up. If they addressed your objection with a real "
                "adjustment, agree or say you're tempted. If they ignored it or just repeated themselves, stay "
                "friendly but unconvinced. One or two sentences, no further questions.",
                "Okay, Sunday afternoon could actually work. You've sold me — text me the details.",
            ),
        ),
        max_user_turns=2,
        demo_answers=(
            "We should go to the night market by the river on Saturday. There's live music, loads of cheap "
            "food stalls, and you said you like trying new food, so I think you'd love it.",
            "Oh, okay, that's fair. What if we go Sunday afternoon instead? It's quieter then, and we could "
            "grab dumplings and still be home early so you can rest.",
        ),
    ),
    "tell_a_story": Activity(
        id="tell_a_story",
        title="Tell a story",
        prompt="Tell me about a time something didn't go as planned. It can be funny, ordinary, or meaningful.",
        duration_label="2–3 min",
        suggested_seconds=120,
        minutes=3,
        dimensions=("storytelling", "structure", "clarity"),
        context="Tell Maya a story. Any size is fine — a burnt dinner counts.",
        tips=("Start wherever feels natural.", "Small stories work well."),
        steps=(
            Step(
                "missing_piece",
                "Ask about ONE missing detail or consequence in their story — e.g. \"What happened next?\" or "
                "\"What made that moment stick with you?\" — choosing whichever fits what they left out.",
                "Oh no! What happened next?",
            ),
            Step("close", CLOSE_INSTRUCTION, "That's such a good story — I'm going to remember that one."),
        ),
        max_user_turns=2,
        demo_answers=(
            "So last spring I planned this big surprise picnic for my partner's birthday. I'd booked the "
            "perfect spot by the lake, made all their favorite food, and the second we sat down the sky just "
            "opened. Total downpour. We ended up eating cake in the car with the windows fogged up.",
            "And honestly it became the best part. We laughed so much, and now every birthday we eat cake in "
            "the car on purpose. It taught me the plan matters less than who you're with.",
        ),
    ),
}

ACTIVITY_ORDER: tuple[str, ...] = (
    "meet_someone_new",
    "explain_interest",
    "respond_to_someone",
    "make_a_case",
    "tell_a_story",
)

# Smallest activity that creates an opportunity for each dimension (used for gap-filling).
GAP_ACTIVITY: dict[str, str] = {
    "clarity": "explain_interest",
    "structure": "explain_interest",
    "concision": "explain_interest",
    "listening": "respond_to_someone",
    "warmth": "meet_someone_new",
    "persuasion": "make_a_case",
    "storytelling": "tell_a_story",
}

GAP_TITLES: dict[str, str] = {
    "listening": "Try a short listening scenario",
    "warmth": "Have a quick chat with someone new",
    "persuasion": "Make a quick case",
    "storytelling": "Tell a short story",
    "clarity": "Explain something you know",
    "structure": "Explain something you know",
    "concision": "Explain something you know",
}


def assessment_estimate_minutes(activity_ids: list[str] | tuple[str, ...]) -> list[int]:
    total = sum(ACTIVITIES[a].minutes for a in activity_ids)
    if set(activity_ids) == set(ACTIVITY_ORDER):
        return [10, 15]
    return [max(1, total), max(2, total + 2)]
