"""Prompt builders. Each returns (instructions, input_text) for the Responses API.

The rules here are the product's evidence policy in words; server-side guards in
`domain/evidence.py` and `services/analysis.py` enforce the same rules in code.
"""

from __future__ import annotations

from ..domain.archetypes import STYLE_ARCHETYPES
from ..domain.dimensions import DIMENSIONS, rubric_text
from ..domain.evidence import Unit
from ..domain.languages import language_name
from .types import (
    AssessmentRequest,
    AttemptRequest,
    CustomScenarioRequest,
    DebriefRequest,
    EventPrepRequest,
    PartnerReplyRequest,
    ReflectionRequest,
    SparRequest,
    WeeklyRequest,
)


def _fmt_time(seconds: float | None) -> str:
    if seconds is None:
        return ""
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


def transcript_block(units: list[Unit]) -> str:
    """One line per unit: `[id] ROLE (name, time): text`. Excluded user lines are shown but marked."""
    lines: list[str] = []
    for unit in units:
        role = {"user": "USER", "partner": "PARTNER", "other": "OTHER"}[unit.role]
        time = f", {_fmt_time(unit.start)}" if unit.source_type == "recording" and unit.start is not None else ""
        name = f"{unit.speaker_name}{time}"
        flag = f" [EXCLUDED: {unit.exclusion_reason or 'unclear'} — do not assess]" if unit.excluded else ""
        lines.append(f"[{unit.uid}] {role} ({name}){flag}: {unit.text.strip()}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- partner


def partner_reply(req: PartnerReplyRequest) -> tuple[str, str]:
    parts = [
        f"You are role-playing {req.partner_name} ({req.partner_role}) in a spoken practice conversation.",
        f"Character: {req.partner_character}",
        f"Situation: {req.situation}",
    ]
    if req.difficulty_behaviour:
        parts.append(f"Difficulty — {req.difficulty_behaviour}")
    if req.win_condition:
        parts.append(f"What would genuinely persuade or satisfy you: {req.win_condition}")
    parts.append(
        "How to speak:\n"
        f"- Natural spoken {language_name(req.language)}. 1–2 short sentences, at most about 35 words.\n"
        "- Contractions, no lists, no emoji, no stage directions, no quotation marks around your line.\n"
        "- Stay in character. Never coach, evaluate, or mention practice, apps, AI or assessments.\n"
        "- React to what the user ACTUALLY said; reference a specific detail when natural. Never invent things "
        "they said. If their turn is unclear, respond naturally to what you can make out."
    )
    parts.append(f"Your job right now: {req.step_instruction}")
    if req.is_closing:
        parts.append("This is your final line in this conversation: set end_conversation to true.")
    else:
        parts.append(
            "Set end_conversation to false unless the scenario has clearly and naturally concluded."
            if req.kind == "spar"
            else "Set end_conversation to false."
        )
    if req.want_coach_whisper:
        parts.append(
            "coach_whisper: one short, specific, actionable hint for the user about their LAST turn, as a coach "
            "would whisper it (max 18 words), e.g. \"You're hedging — lead with the number.\" Null if nothing "
            "useful to add."
        )
    else:
        parts.append("coach_whisper must be null.")
    if req.want_momentum:
        parts.append(
            "momentum: 0–1, how persuaded/comfortable you (the character) now feel given the whole conversation. "
            "outcome_label: if the scenario resolves (you agree or firmly decline), a 2–4 word label like "
            "'Budget approved' or 'Not convinced'; otherwise null."
        )
    else:
        parts.append("momentum and outcome_label must be null.")
    if req.turns_left <= 1 and req.kind == "spar" and not req.is_closing:
        parts.append("The conversation is nearly over: move toward a natural decision.")

    history = "\n".join(f"{speaker}: {text}" for speaker, text in req.history)
    return "\n\n".join(parts), f"CONVERSATION SO FAR:\n{history}"


# --------------------------------------------------------------------------- assessment

ASSESSOR_RULES = """You are Comlogue's communication assessor. From a sample of conversation you produce an
INITIAL, EVIDENCE-BASED communication profile. You are careful, kind and specific.

Non-negotiable rules:
1. Assess ONLY the user's speech (segments labelled USER). PARTNER (an AI character) and OTHER (other people in
   a recording) are context only: never credit or blame the user for them, and never evaluate those people.
2. Evidence first. For each of the seven dimensions decide whether this sample gave the user a real opportunity
   to show it, and how much usable evidence exists: none, limited or sufficient. The system has computed the
   maximum strength the sample's structure allows (the CAP); never exceed it.
3. Give a level (1–5, rubric below) ONLY when evidence is limited or sufficient. Otherwise level, confidence,
   summary and one_change must be null and evidence must be empty. Missing evidence is never a low level.
4. Every assessed dimension cites 1–3 moments by segment_id with a short verbatim quote from a USER segment that
   is not EXCLUDED. If you cannot point to a moment, the evidence is none.
5. Never assess accent, pronunciation, grammar typical of non-native speakers, voice or audio quality. If a line
   looks garbled or mis-transcribed, ignore it rather than judging it — abstain when uncertain.
6. Describe the sample, not the person: "In this conversation you…", never "You are…". No diagnosis language,
   no labels, no overall score, no comparisons with other people.
7. Communication norms (directness, warmth, turn-taking, storytelling) vary across cultures and languages. Don't
   penalize a style that fits a different norm; judge whether it worked for this listener in this context.
8. Concision is not brevity: a shorter answer is not automatically better.
9. Confidence describes the evidence (how much, how clear), not the user's skill.
10. Strengths and changes must reference what actually happened. Warm, concrete, never generic.
"""


def assessment(req: AssessmentRequest) -> tuple[str, str]:
    archetypes = "\n".join(f"- {name}: {desc}" for name, desc in STYLE_ARCHETYPES.items())
    instructions = (
        f"{ASSESSOR_RULES}\n"
        "first_win: pick the single most useful moment to rewrite — a real USER segment where one small change "
        "would most help an assessed dimension. Rewrite it in the user's own voice, keeping their content. Null "
        "if nothing is assessed.\n\n"
        "style: only when STYLE ELIGIBLE is yes and the user's speech shows a consistent pattern across "
        "activities. Choose the closest archetype, describe it observationally ('In these conversations you "
        "tended to…') and list 2–3 observable traits. Never infer personality. If not eligible: eligible=false "
        "and null/empty fields.\n\n"
        f"Archetypes:\n{archetypes}\n\n"
        f"Return all seven dimensions. Write every user-facing string in {language_name(req.language)}.\n\n"
        f"RUBRIC (levels describe what was observed in this sample):\n{rubric_text()}"
    )
    stats = req.stats
    facts = [
        f"User speech: {int(stats.user_speech_seconds)} s across {stats.user_turns} turns "
        f"({stats.extended_turns} extended, {stats.narrative_turns} story-length).",
        f"Exchanges (someone else spoke, then the user replied): {stats.exchanges} "
        f"({stats.substantive_exchanges} substantive).",
    ]
    if stats.excluded_user_units:
        reasons = ", ".join(f"{k} ×{v}" for k, v in stats.excluded_reasons.items())
        facts.append(f"Excluded user segments (not assessable): {stats.excluded_user_units} ({reasons}).")
    caps = []
    for dim_id in DIMENSIONS:
        cap = req.caps[dim_id]
        line = f"- {dim_id}: {cap.max_strength}"
        if cap.max_strength == "none" and cap.reason:
            line += f" — {cap.reason}"
        elif cap.needs_model_opportunity:
            line += " (only if you find a real opportunity in the transcript)"
        caps.append(line)
    blocks = [f"CONTEXT: {req.context_description}"]
    if req.activity_notes:
        blocks.append("ACTIVITIES:\n" + "\n".join(req.activity_notes))
    if req.target_dimensions:
        blocks.append("FOCUS (gap-filling task) on: " + ", ".join(req.target_dimensions))
    blocks.append("SAMPLE FACTS (computed by the system, trustworthy):\n" + "\n".join(facts))
    blocks.append("EVIDENCE CAPS (maximum strength you may assign):\n" + "\n".join(caps))
    blocks.append(f"STYLE ELIGIBLE: {'yes' if req.style_eligible else 'no'}")
    blocks.append("TRANSCRIPT:\n" + transcript_block(req.units))
    return instructions, "\n\n".join(blocks)


# --------------------------------------------------------------------------- missions


def attempt_feedback(req: AttemptRequest) -> tuple[str, str]:
    instructions = (
        "You are Comlogue's practice coach. You give feedback on ONE attempt at ONE target behavior.\n"
        f"TARGET BEHAVIOR: {req.target_behavior}\n\n"
        "Rules:\n"
        "- Judge only the USER's lines against the target. The PARTNER line is context.\n"
        "- assessable: yes (clear user speech that addresses the task), partly (some of it unclear, very short or "
        "off-task), no (nothing usable). If no, target_met must be 'unclear' and where_* null.\n"
        "- target_met: yes / partly / no / unclear. where_segment_id + where_quote (verbatim, ≤ 25 words) point "
        "to where the target behavior appeared, or the closest attempt at it.\n"
        "- what_worked: 0–2 specific things. one_change: exactly one concrete change for the next try.\n"
        "- If a PREVIOUS ATTEMPT is given, compare both against the same target only and fill comparison_summary "
        "and comparison_changes. A shorter answer is not automatically a better one. Otherwise set them to null "
        "and [].\n"
        "- Never assess accent or pronunciation. Speak about the attempt, not the person. Warm, direct, specific.\n"
        f"- Write in {language_name(req.language)}."
    )
    blocks = [
        f"MISSION: {req.mission_title}",
        f"SITUATION: {req.context}",
        f"ATTEMPT {'(quick 2-minute version)' if req.quick else ''}:\n{transcript_block(req.units)}",
    ]
    if req.previous_units:
        blocks.append("PREVIOUS ATTEMPT:\n" + transcript_block(req.previous_units))
        if req.previous_headline:
            blocks.append(f"Previous feedback headline: {req.previous_headline}")
    return instructions, "\n\n".join(blocks)


def spar_report(req: SparRequest) -> tuple[str, str]:
    instructions = (
        "You are Comlogue's sparring coach. Review a practice roleplay and write a short report.\n"
        "- outcome: did the partner end up persuaded/satisfied? Base it on the partner's final lines.\n"
        "- momentum_notes: for 1–3 partner turns where momentum shifted, say what the user did that moved it.\n"
        "- moments: 1–3 'rewrite this moment' suggestions from real USER segments (verbatim you_said, an improved "
        "try_instead in the user's voice, one-sentence why).\n"
        "- observations: ONLY for dimensions this conversation gave a real opportunity to show, each citing a USER "
        "segment. Speak about this conversation, not the person. No scores, no grades.\n"
        "- Never assess accent or pronunciation.\n"
        f"- Write in {language_name(req.language)}."
    )
    momentum = ", ".join(f"turn {i}: {v:.2f}" for i, v in req.momentum) or "not recorded"
    blocks = [
        f"PARTNER: {req.persona_name}, {req.persona_title}. Scenario: {req.scenario}. Difficulty: {req.difficulty}.",
        f"What would have persuaded them: {req.win_condition}",
        f"Momentum recorded during the conversation: {momentum}",
        "TRANSCRIPT:\n" + transcript_block(req.units),
    ]
    return instructions, "\n\n".join(blocks)


def reflection_reply(req: ReflectionRequest) -> tuple[str, str]:
    instructions = (
        "You are Comlogue's coach replying to a user's reflection on a real-life mission. Reply in 2–3 sentences: "
        "acknowledge what they did (trying counts, whatever the outcome), offer one insight tied to the target "
        "behavior, and suggest one tiny next step. This is self-report — do not evaluate their skill or invent "
        "details. No toxic positivity, no guilt. "
        f"Write in {language_name(req.language)}."
    )
    went = f"They said it went: {req.went}." if req.went else ""
    text = (
        f"MISSION: {req.mission_title}\nTARGET: {req.target_behavior}\nREAL-LIFE PROMPT: {req.real_life_prompt}\n"
        f"{went}\nREFLECTION: {req.text}"
    )
    return instructions, text


def event_prep(req: EventPrepRequest) -> tuple[str, str]:
    instructions = (
        "You design rehearsal scenarios for a communication-practice app. Create exactly 3 short roleplay "
        "scenarios that prepare the user for their upcoming event, easiest first (difficulty kind, then real, then "
        "real or brutal). Each scenario is written in the second person, is realistic, and has a clear partner "
        "role. Keep everything respectful and safe. "
        f"Write in {language_name(req.language)}."
    )
    notes = f"\nNOTES: {req.notes}" if req.notes else ""
    return instructions, f"EVENT: {req.title}\nKIND: {req.kind}\nDATE: {req.date}\nGOAL AREA: {req.goal_title}{notes}"


def weekly(req: WeeklyRequest) -> tuple[str, str]:
    instructions = (
        "You write the weekly review in a communication-practice app. Use ONLY the facts given — never invent "
        "progress or skill changes. 2–3 specific highlights, then a warm, honest 2-sentence message. If the user "
        "missed their target, no guilt: make the next step feel easy. Practice completion is not skill. "
        f"Write in {language_name(req.language)}."
    )
    return instructions, f"CURRENT FOCUS: {req.focus_title}\nFACTS:\n" + "\n".join(f"- {f}" for f in req.facts)


def debrief(req: DebriefRequest) -> tuple[str, str]:
    instructions = (
        "You debrief a recorded conversation for the USER. Identify: the user's best moment (a USER segment id and "
        "a short note on why it worked), decisions or agreements made (by anyone; empty if none), a short follow-up "
        "message the user could send to the others, and one thing the USER could try next time about their own "
        "behavior. Never evaluate the other participants. If there's nothing meaningful, use nulls/empty lists. "
        f"Write in {language_name(req.language)}."
    )
    share = ", ".join(f"{name}{' (user)' if is_user else ''}: {round(s * 100)}%" for name, s, is_user in req.talk_share)
    return instructions, f"TITLE: {req.title}\nTALK SHARE: {share}\nTRANSCRIPT:\n{transcript_block(req.units)}"


def custom_scenario(req: CustomScenarioRequest) -> tuple[str, str]:
    instructions = (
        "Turn the user's described practice scenario into a roleplay partner for a communication-practice app. "
        "Give a first name, a role, an in-character opening line (1–2 sentences, spoken), a one-sentence context "
        "in the second person, a short character description (what they care about), and what would genuinely "
        "persuade or satisfy them. Keep it realistic and respectful; if the request is unsafe or sexual, create a "
        "safe, professional version instead. Do not impersonate real, named people. "
        f"Write in {language_name(req.language)}."
    )
    return instructions, f"SCENARIO: {req.scenario}\nDIFFICULTY: {req.difficulty}"
