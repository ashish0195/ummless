"""Developer tool: seed a rich, realistic demo state for the calling user (no audio, no AI calls).

Used for screenshots, design QA and App Review demos. Only available when dev entitlements are allowed.
Everything is built from the same API schemas as real results, so the app renders it exactly like real data.
Idempotent per user: a second call returns the same ids.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ..core import AppServices
from ..domain.activities import ACTIVITIES, ACTIVITY_ORDER, MAYA, MAYA_CHARACTER, MAYA_TTS_INSTRUCTIONS
from ..domain.consents import ANALYSIS_VERSION
from ..domain.course import MISSIONS, MODULES
from ..domain.dimensions import DIMENSIONS, level_label
from ..domain.personas import PERSONAS
from ..ids import new_id
from ..models import (
    ActivityLog,
    Assessment,
    Conversation,
    DimensionEstimate,
    MissionAttempt,
    MissionProgress,
    Recording,
    Reflection,
    SparReport,
    Turn,
    UpcomingEvent,
    User,
)
from ..schemas import (
    AnalysisResult,
    AttemptFeedback,
    Comparison,
    ConversationSetup,
    DemoSeedResult,
    DimensionResult,
    EvidenceMoment,
    MeetingDebrief,
    MomentumPoint,
    Observation,
    Recovery,
    RecoveryAction,
    RewriteMoment,
    SparOutcome,
    SparReportOut,
    SpeechPatterns,
    StyleResult,
    TalkShare,
)
from ..timeutil import iso_required, short_date, utcnow, week_bounds
from . import billing, progress, users
from .analysis import missing_dimension, partial_message
from .course import COMPARISON_NOTE

FREE_MISSION = "business.m1.learn"


class _Clock:
    """Timestamps spread over the current week so progress and the weekly review look alive."""

    def __init__(self) -> None:
        self.now = utcnow()
        week_start, _ = week_bounds(self.now)
        self.base = max(week_start + timedelta(minutes=5), self.now - timedelta(hours=8))

    def at(self, fraction: float) -> datetime:
        return (self.base + (self.now - self.base) * fraction).replace(microsecond=0)


def _moment(quote: str, note: str, source_type: str, source_id: str, turn_index: int | None = None,
            start: float | None = None, end: float | None = None) -> EvidenceMoment:
    return EvidenceMoment(quote=quote, note=note, source_type=source_type, source_id=source_id,  # type: ignore[arg-type]
                          turn_index=turn_index, start_seconds=start, end_seconds=end, audio_url=None)


def _assessed(dim: str, status: str, level: int, confidence: str, summary: str, strength: str, change: str,
              evidence: list[EvidenceMoment], when: datetime, context: str) -> DimensionResult:
    return DimensionResult(
        dimension=dim, title=DIMENSIONS[dim].title, status=status, level=level, level_label=level_label(level),  # type: ignore[arg-type]
        confidence=confidence, summary=summary, strengths=[strength], one_change=change, evidence=evidence,  # type: ignore[arg-type]
        missing_reason=None, next_step=None, assessed_at=iso_required(when), context_label=context,
    )


def _conversation(db: Session, user: User, *, kind: str, partner: dict[str, Any], setup: ConversationSetup,
                  turns: list[dict[str, Any]], when: datetime, state: dict[str, Any] | None = None,
                  **fields: Any) -> Conversation:
    conv = Conversation(
        id=new_id("cnv"), user_id=user.id, kind=kind, status="finished", awaiting="none", partner=partner,
        setup=setup.model_dump(mode="json"), state=state or {}, created_at=when, finished_at=when + timedelta(minutes=4),
        user_turns=sum(1 for t in turns if t["speaker"] == "user"), demo_mode=True, **fields,
    )
    db.add(conv)
    db.flush()
    for index, turn in enumerate(turns):
        words = len(turn["text"].split())
        metrics = {"duration": round(words / 2.4, 1), "words": words} if turn["speaker"] == "user" else {}
        quality = ({"usable": "yes", "issues": [], "speech_seconds": metrics.get("duration", 0.0),
                    "duration_seconds": metrics.get("duration", 0.0)} if turn["speaker"] == "user" else None)
        db.add(Turn(conversation_id=conv.id, index=index, speaker=turn["speaker"], text=turn["text"],
                    created_at=when + timedelta(seconds=20 * index), quality=quality,
                    coach_whisper=turn.get("whisper"), momentum=turn.get("momentum"), metrics=metrics, segments=[]))
    db.flush()
    return conv


def _estimates(db: Session, user: User, dims: list[DimensionResult], source_type: str, source_id: str,
               when: datetime, context: str) -> None:
    for dim in dims:
        if dim.status in ("assessed", "provisional") and dim.level is not None:
            db.add(DimensionEstimate(user_id=user.id, dimension=dim.dimension, status=dim.status, level=dim.level,
                                     confidence=dim.confidence or "low", payload=dim.model_dump(mode="json"),
                                     source_type=source_type, source_id=source_id, context_label=context,
                                     assessed_at=when))


def _log(db: Session, user: User, type_: str, title: str, minutes: float, ref: str, when: datetime) -> None:
    db.add(ActivityLog(user_id=user.id, type=type_, title=title, minutes=minutes, ref_id=ref, created_at=when))


# ------------------------------------------------------------------ pieces


def _seed_assessment(db: Session, user: User, clock: _Clock) -> Assessment:
    when = clock.at(0.1)
    context = f"AI roleplay · {short_date(when)}"
    maya = dict(MAYA)
    state = {"tts_instructions": MAYA_TTS_INSTRUCTIONS, "character": MAYA_CHARACTER}

    def setup(activity_id: str) -> ConversationSetup:
        activity = ACTIVITIES[activity_id]
        return ConversationSetup(title=activity.title, context=activity.context, target_behavior=None,
                                 suggested_seconds=activity.suggested_seconds, tips=list(activity.tips),
                                 activity_id=activity_id, mission_id=None, persona_id=None, difficulty=None,
                                 quick=False)

    assessment = Assessment(id=new_id("asm"), user_id=user.id, route="roleplay", purpose="baseline",
                            status="complete", activity_ids=list(ACTIVITY_ORDER), target_dimensions=[], language="en",
                            created_at=when, completed_at=when + timedelta(minutes=12))
    meet = _conversation(db, user, kind="assessment_activity", partner=maya, setup=setup("meet_someone_new"),
                         when=when, state=state, assessment_id=assessment.id, activity_id="meet_someone_new",
                         max_user_turns=3, turns=[
        {"speaker": "partner", "text": ACTIVITIES["meet_someone_new"].prompt},
        {"speaker": "user", "text": "Lately I've been getting into sourdough baking. I started during a long winter and, "
                                    "um, now I bake every weekend and give most of it away to my neighbors."},
        {"speaker": "partner", "text": "Oh nice — your neighbors must love you. What got you into it in the first place?"},
        {"speaker": "user", "text": "A friend gave me some starter and I didn't want to kill it, so I just kept feeding "
                                    "it. One thing led to another, honestly."},
        {"speaker": "partner", "text": "Ha, that's lovely. I've been getting into bouldering — I'm terrible at it, but "
                                       "my rescue dog Biscuit thinks the gym is the best place on earth."},
        {"speaker": "user", "text": "Bouldering sounds fun! How long have you been doing it? And does Biscuit actually "
                                    "come inside the gym?"},
        {"speaker": "partner", "text": "Ha, I love that. It's really nice to meet you."},
    ])
    explain = _conversation(db, user, kind="assessment_activity", partner=maya, setup=setup("explain_interest"),
                            when=when + timedelta(minutes=3), state=state, assessment_id=assessment.id,
                            activity_id="explain_interest", max_user_turns=3, turns=[
        {"speaker": "partner", "text": ACTIVITIES["explain_interest"].prompt},
        {"speaker": "user", "text": "So I'll explain chess. Two players each control sixteen pieces, and the goal is to "
                                    "trap the other player's king so it can't escape. Each piece moves differently, "
                                    "and early on you want to control the center of the board, because pieces in the "
                                    "middle can reach more squares."},
        {"speaker": "partner", "text": "Wait, sorry — what does controlling the center actually mean in practice?"},
        {"speaker": "user", "text": "It means putting your pieces on the four middle squares, or attacking them, so you "
                                    "have more options than your opponent."},
        {"speaker": "partner", "text": "Got it, thanks. What's the main thing you'd want me to remember?"},
        {"speaker": "user", "text": "Every move should give you more options and your opponent fewer."},
        {"speaker": "partner", "text": "That makes sense — I think I'd actually remember that."},
    ])
    case = _conversation(db, user, kind="assessment_activity", partner=maya, setup=setup("make_a_case"),
                         when=when + timedelta(minutes=7), state=state, assessment_id=assessment.id,
                         activity_id="make_a_case", max_user_turns=2, turns=[
        {"speaker": "partner", "text": ACTIVITIES["make_a_case"].prompt},
        {"speaker": "user", "text": "I think we should, kind of, go to the night market by the river on Saturday? "
                                    "There's live music and lots of cheap food, and you said you like trying new "
                                    "things."},
        {"speaker": "partner", "text": "Hmm, it sounds fun, but I'm on a night shift Saturday, so I'll be wrecked most "
                                       "of the day."},
        {"speaker": "user", "text": "Oh, that's fair. What if we go Sunday afternoon instead? It's quieter, we can grab "
                                    "dumplings, and you'll still be home early to rest."},
        {"speaker": "partner", "text": "Okay, Sunday afternoon could actually work. You've sold me — text me the "
                                       "details."},
    ])
    assessment.activity_state = {
        "meet_someone_new": {"status": "done", "conversation_id": meet.id},
        "explain_interest": {"status": "done", "conversation_id": explain.id},
        "respond_to_someone": {"status": "skipped", "conversation_id": None},
        "make_a_case": {"status": "done", "conversation_id": case.id},
        "tell_a_story": {"status": "skipped", "conversation_id": None},
    }
    done = when + timedelta(minutes=12)
    dims = [
        _assessed("clarity", "assessed", 4, "moderate",
                  "In this conversation your explanation had a clear goal and a concrete principle.",
                  "You explained chess with one memorable principle: control the center.",
                  "Say your main point first, then the example.",
                  [_moment("The goal is to trap the other player's king so it can't escape.", "Main point stated early",
                           "conversation", explain.id, 1),
                   _moment("Every move should give you more options and your opponent fewer.",
                           "A memorable one-line summary", "conversation", explain.id, 5)], done, context),
        _assessed("structure", "provisional", 3, "low",
                  "Your longer answer had a recognizable shape — goal, rules, then strategy — with one detour.",
                  "You ended with a clear takeaway.",
                  "Signpost the parts: \"Two things matter — the goal, and the center.\"",
                  [_moment("Two players each control sixteen pieces, and the goal is to trap the other player's king.",
                           "Goal before detail", "conversation", explain.id, 1)], done, context),
        missing_dimension("listening", "There wasn't enough clear back-and-forth to assess listening."),
        _assessed("warmth", "assessed", 4, "moderate",
                  "You showed real interest in Maya and asked about her climbing and her dog.",
                  "You asked a follow-up about something Maya had just shared.",
                  "Use her words back: \"You said you're terrible at it — what keeps you going?\"",
                  [_moment("Bouldering sounds fun! How long have you been doing it?", "Curious about her",
                           "conversation", meet.id, 5)], done, context),
        _assessed("persuasion", "assessed", 3, "moderate",
                  "When Maya objected, you adapted with an alternative that addressed her concern.",
                  "You changed the plan to fit her night shift.",
                  "Lead with what's in it for her before the logistics.",
                  [_moment("What if we go Sunday afternoon instead?", "Adapted to the objection", "conversation",
                           case.id, 3)], done, context),
        _assessed("concision", "assessed", 2, "moderate",
                  "Your points were there, but warm-up phrases like \"I think\" and \"kind of\" delayed them.",
                  "Your Sunday suggestion was short and specific.",
                  "Cut the warm-up: start with the suggestion itself.",
                  [_moment("I think we should, kind of, go to the night market by the river on Saturday?",
                           "The suggestion arrives after two hedges", "conversation", case.id, 1)], done, context),
        missing_dimension("storytelling", "We didn't hear a story in this sample."),
    ]
    assessed = [d.dimension for d in dims if d.status in ("assessed", "provisional")]
    missing = [d.dimension for d in dims if d.status not in ("assessed", "provisional")]
    message = partial_message(assessed, missing)
    result = AnalysisResult(
        status="partial", headline="Your partial communication profile", summary=message, dimensions=dims,
        speech_patterns=SpeechPatterns(words_per_minute=164, filler_per_minute=1.8, top_fillers=["um", "like"],
                                       hedges_per_minute=2.3, avg_pause_seconds=0.52, longest_turn_seconds=41.0,
                                       talk_share=None, user_speech_seconds=236.0, language_supported=True),
        first_win=RewriteMoment(dimension="concision",
                                you_said="I think we should, kind of, go to the night market by the river on Saturday?",
                                try_instead="Let's go to the night market by the river on Saturday — live music and "
                                            "cheap food.",
                                why="Starting with the suggestion makes it sound like a plan, not a question.",
                                source_type="conversation", source_id=case.id, turn_index=1, start_seconds=None,
                                end_seconds=None, audio_url=None),
        style=StyleResult(status="provisional", archetype="The Explainer",
                          description="In these conversations you tended to explain with concrete examples and check "
                                      "that the other person was following. This is an early read from a few short "
                                      "samples.",
                          traits=["Concrete examples", "Checks in with the listener", "Warm, curious questions"],
                          message="An early read from a few conversations — it may change as we hear more."),
        recovery=Recovery(problem="too_little_evidence", title="Fill the gaps when you're ready", message=message,
                          actions=[RecoveryAction(type="gap_fill", title="Try a short listening scenario",
                                                  activity_id="respond_to_someone"),
                                   RecoveryAction(type="gap_fill", title="Tell a short story", activity_id="tell_a_story"),
                                   RecoveryAction(type="upload_another", title="Upload another conversation",
                                                  activity_id=None),
                                   RecoveryAction(type="continue", title="Continue with my current results",
                                                  activity_id=None)],
                          extra_minutes=6),
        context_label=context, created_at=iso_required(done),
    )
    assessment.result = result.model_dump(mode="json")
    assessment.style_vector = {"wpm": 164.0, "avg_pause_seconds": 0.52, "sentence_words": 14.0,
                               "questions_per_min": 1.1, "hedges_per_min": 2.3}
    db.add(assessment)
    _estimates(db, user, dims, "assessment", assessment.id, done, context)
    _log(db, user, "assessment", context, 9.5, assessment.id, done)
    return assessment


def _segments(lines: list[tuple[str, float, float, str]]) -> list[dict[str, Any]]:
    return [{"index": i, "speaker": speaker, "start": start, "end": end, "text": text, "excluded": False,
             "exclusion_reason": None} for i, (speaker, start, end, text) in enumerate(lines)]


def _seed_complete_recording(db: Session, user: User, clock: _Clock) -> Recording:
    when = clock.at(0.45)
    rec_id = new_id("rec")
    title = "1:1 with Priya"
    context = f"{title} · {short_date(when)}"
    segments = _segments([
        ("A", 2.0, 14.5, "So, um, I guess the main thing, if that's okay, is maybe we look at the launch review "
                         "timing? I know it's been a busy week."),
        ("B", 15.2, 24.0, "Yeah, it has. Honestly I'm worried about the pricing page, it's not ready."),
        ("A", 24.6, 29.8, "What's worrying you most about the pricing page?"),
        ("B", 30.5, 46.0, "The copy still talks about the old plans, and legal hasn't seen the new terms. I don't "
                          "want us launching with the wrong prices."),
        ("A", 46.8, 60.0, "That makes sense. So it's the copy and the legal review — not the design. If we moved the "
                          "launch review to Thursday, would that give you enough time?"),
        ("B", 60.6, 66.0, "Thursday would work if I can focus on it."),
        ("A", 66.5, 80.0, "Thanks for flagging that — I know you're stretched this week. I'll take the partner "
                          "update off your plate, and I'll review the copy Wednesday."),
        ("B", 80.4, 85.0, "That really helps. Okay, Thursday it is."),
    ])
    dims = [
        _assessed("clarity", "provisional", 3, "low", "Your main ask came through, after some background.",
                  "You named the decision clearly once you got there.",
                  "Open with the topic and the ask: \"Main thing today: can we move the launch review?\"",
                  [_moment("If we moved the launch review to Thursday, would that give you enough time?",
                           "The ask, clearly stated", "recording", rec_id, None, 46.8, 60.0)], when, context),
        missing_dimension("structure", "We need at least one longer answer to see how you organize your ideas."),
        _assessed("listening", "assessed", 3, "moderate",
                  "You asked Priya about her concern before suggesting a fix, and summarized what you heard.",
                  "You summarized her concern before proposing a change.",
                  "Ask one more open question before you propose the fix.",
                  [_moment("What's worrying you most about the pricing page?", "Asked before advising", "recording",
                           rec_id, None, 24.6, 29.8),
                   _moment("So it's the copy and the legal review — not the design.", "Checked understanding",
                           "recording", rec_id, None, 46.8, 60.0)], when, context),
        _assessed("warmth", "assessed", 4, "moderate",
                  "You acknowledged Priya's workload and offered to take something off her plate.",
                  "You thanked her for flagging the risk.", "Keep it — and name the impact of her work in the recap.",
                  [_moment("Thanks for flagging that — I know you're stretched this week.", "Acknowledged her load",
                           "recording", rec_id, None, 66.5, 80.0)], when, context),
        missing_dimension("persuasion", "There wasn't a moment where you made a case or responded to an objection."),
        _assessed("concision", "assessed", 3, "moderate", "Most of your turns were to the point; the opening ran long.",
                  "Your question about the pricing page was short and open.",
                  "Drop \"I guess\" and \"if that's okay\" from your opener.",
                  [_moment("So, um, I guess the main thing, if that's okay, is maybe we look at the launch review "
                           "timing?", "A long warm-up before the topic", "recording", rec_id, None, 2.0, 14.5)],
                  when, context),
        missing_dimension("storytelling", "We didn't hear a story in this sample."),
    ]
    assessed = [d.dimension for d in dims if d.status in ("assessed", "provisional")]
    missing = [d.dimension for d in dims if d.status not in ("assessed", "provisional")]
    message = partial_message(assessed, missing)
    result = AnalysisResult(
        status="partial", headline="Clear, kind and curious in this 1:1", summary=message, dimensions=dims,
        speech_patterns=SpeechPatterns(words_per_minute=151, filler_per_minute=2.4, top_fillers=["um", "you know"],
                                       hedges_per_minute=1.6, avg_pause_seconds=0.61, longest_turn_seconds=52.0,
                                       talk_share=0.57, user_speech_seconds=690.0, language_supported=True),
        first_win=RewriteMoment(dimension="concision",
                                you_said="So, um, I guess the main thing, if that's okay, is maybe we look at the "
                                         "launch review timing?",
                                try_instead="Main thing today: can we move the launch review to Thursday?",
                                why="Naming the topic and the ask up front gives Priya something to respond to.",
                                source_type="recording", source_id=rec_id, turn_index=None, start_seconds=2.0,
                                end_seconds=14.5, audio_url=None),
        style=StyleResult(status="not_ready", archetype=None, description=None, traits=[],
                          message="We need more conversation to describe your style."),
        recovery=Recovery(problem="too_little_evidence", title="Fill the gaps when you're ready", message=message,
                          actions=[RecoveryAction(type="gap_fill", title="Make a quick case", activity_id="make_a_case"),
                                   RecoveryAction(type="gap_fill", title="Explain something you know",
                                                  activity_id="explain_interest"),
                                   RecoveryAction(type="upload_another", title="Upload another conversation",
                                                  activity_id=None),
                                   RecoveryAction(type="continue", title="Continue with my current results",
                                                  activity_id=None)],
                          extra_minutes=5),
        context_label=context, created_at=iso_required(when),
    )
    debrief = MeetingDebrief(
        talk_share=[TalkShare(label="A", display_name="You", is_user=True, share=0.57),
                    TalkShare(label="B", display_name="Speaker 2", is_user=False, share=0.43)],
        best_moment=_moment("What's worrying you most about the pricing page?",
                            "You asked before advising — Priya's answer changed the plan.", "recording", rec_id, None,
                            24.6, 29.8),
        decisions=["Move the launch review to Thursday.",
                   "Priya owns the pricing page copy; you'll review it on Wednesday."],
        follow_up_summary="Thanks for today, Priya — quick recap: we're moving the launch review to Thursday, and "
                          "you'll own the pricing page copy. I'll review it Wednesday and take the partner update off "
                          "your plate.",
        one_thing_to_try="You spoke 57% of the time. Next 1:1, ask one open question before sharing your view.",
    )
    recording = Recording(
        id=rec_id, user_id=user.id, title=title, source="live", status="complete", stage=None, duration_seconds=1260.0,
        analyzed_seconds=1260.0, language="en",
        consent={"attested": True, "region": "US-CA", "rule": "all_party", "consent_version": "recording-2026-10",
                 "accepted_at": iso_required(when)},
        quality={"usable": "yes", "issues": [], "usable_seconds": 1180.0, "total_seconds": 1260.0},
        segments=segments,
        speakers=[
            {"label": "A", "display_name": "Speaker 1", "speech_seconds": 690.0, "turns": 24, "sample_url": None,
             "sample_text": "So the main thing I want to cover is the launch review timing.", "is_proposed_user": True,
             "match": "reference", "match_strength": "strong"},
            {"label": "B", "display_name": "Speaker 2", "speech_seconds": 520.0, "turns": 22, "sample_url": None,
             "sample_text": "Honestly I'm worried about the pricing page, it's not ready.", "is_proposed_user": False,
             "match": "none", "match_strength": None},
        ],
        attribution={"status": "confirmed", "user_speaker_label": "A", "requires_confirmation": False, "reason": None,
                     "message": None},
        result=result.model_dump(mode="json"), debrief=debrief.model_dump(mode="json"), recovery=None,
        style_vector={"wpm": 151.0, "avg_pause_seconds": 0.61, "sentence_words": 13.0, "questions_per_min": 0.9,
                      "hedges_per_min": 1.6},
        created_at=when - timedelta(minutes=21), completed_at=when,
    )
    db.add(recording)
    _estimates(db, user, dims, "recording", rec_id, when, context)
    _log(db, user, "recording", title, 21.0, rec_id, when)
    return recording


def _seed_pending_recording(db: Session, user: User, clock: _Clock) -> Recording:
    when = clock.at(0.9)
    recording = Recording(
        id=new_id("rec"), user_id=user.id, title="Product sync", source="upload", status="needs_speaker_confirmation",
        stage=None, duration_seconds=1520.0, analyzed_seconds=1520.0, language="en",
        consent={"attested": True, "region": "US-CA", "rule": "all_party", "consent_version": "recording-2026-10",
                 "accepted_at": iso_required(when)},
        quality={"usable": "partly",
                 "issues": [{"code": "overlapping_voices", "title": "Voices overlapped a lot",
                             "detail": "We skipped parts where people talked over each other, because we can't tell "
                                       "who said what.", "severity": "warning"}],
                 "usable_seconds": 1290.0, "total_seconds": 1520.0},
        segments=_segments([
            ("A", 1.0, 12.0, "Okay, let's start with the roadmap. I think we need to cut scope for the first quarter, "
                             "because the team can't ship all six features well."),
            ("B", 12.5, 22.0, "Before we cut anything, can we look at what customers actually asked for? I don't want "
                              "to drop the export fix."),
            ("A", 22.4, 36.0, "That's fair. My recommendation is we keep the export fix and the onboarding changes, and "
                              "move the dashboard redesign to the second quarter. Two reasons: support tickets, and "
                              "the dashboard needs research first."),
            ("C", 36.5, 42.0, "I can pull the support data by Thursday so we can check that."),
            ("A", 42.3, 50.0, "Great, thanks. Does anyone see a reason not to move the dashboard?"),
            ("B", 50.5, 58.0, "Sales might push back, they promised it to two customers."),
            ("A", 58.4, 72.0, "Okay. Then let's talk to sales today, explain the trade-off, and offer those two "
                              "customers early access to the research sessions instead."),
            ("C", 72.5, 76.0, "Sounds good to me."),
        ]),
        speakers=[
            {"label": "A", "display_name": "Speaker 1", "speech_seconds": 610.0, "turns": 31, "sample_url": None,
             "sample_text": "Okay, let's start with the roadmap. I think we need to cut scope for the first quarter.",
             "is_proposed_user": True, "match": "reference", "match_strength": "weak"},
            {"label": "B", "display_name": "Speaker 2", "speech_seconds": 540.0, "turns": 27, "sample_url": None,
             "sample_text": "Before we cut anything, can we look at what customers actually asked for?",
             "is_proposed_user": False, "match": "none", "match_strength": None},
            {"label": "C", "display_name": "Speaker 3", "speech_seconds": 210.0, "turns": 9, "sample_url": None,
             "sample_text": "I can pull the support data by Thursday so we can check that.", "is_proposed_user": False,
             "match": "none", "match_strength": None},
        ],
        attribution={"status": "pending", "user_speaker_label": None, "requires_confirmation": True,
                     "reason": "uncertain_match", "message": "We think this is you, but we're not sure. Check the line we heard from them."},
        created_at=when,
    )
    db.add(recording)
    return recording


def _seed_mission(db: Session, user: User, clock: _Clock) -> str:
    mission = MISSIONS[FREE_MISSION]
    module = MODULES[mission.module_id]
    partner_def = mission.partner
    assert partner_def is not None
    partner = {"name": partner_def.name, "role": partner_def.role, "voice": partner_def.voice,
               "symbol": partner_def.symbol, "color_hex": partner_def.color_hex}
    setup = ConversationSetup(title=mission.title, context=mission.context, target_behavior=module.target_behavior,
                              suggested_seconds=mission.suggested_seconds,
                              tips=[f"Target: {module.target_behavior}"], activity_id=None, mission_id=mission.id,
                              persona_id=None, difficulty=None, quick=False)
    first_when, second_when = clock.at(0.55), clock.at(0.6)
    first = _conversation(db, user, kind="mission", partner=partner, setup=setup, when=first_when,
                          mission_id=mission.id, max_user_turns=2, turns=[
        {"speaker": "partner", "text": partner_def.opening},
        {"speaker": "user", "text": "Hmm, so there are two options, and I think both have pros and cons. The new one "
                                    "is cheaper but we don't know them, and the old one is familiar… so maybe we go "
                                    "with the new one?"},
        {"speaker": "partner", "text": partner_def.follow_up_fallback},
        {"speaker": "user", "text": "That's true. I guess we could ask them how long onboarding usually takes."},
        {"speaker": "partner", "text": "Okay, that's helpful. Thanks."},
    ])
    second = _conversation(db, user, kind="mission", partner=partner, setup=setup, when=second_when,
                           mission_id=mission.id, max_user_turns=2, turns=[
        {"speaker": "partner", "text": partner_def.opening},
        {"speaker": "user", "text": "I'd go with the new vendor. They're twenty percent cheaper, and they've already "
                                    "passed our security review. What would you want covered before we sign?"},
        {"speaker": "partner", "text": partner_def.follow_up_fallback},
        {"speaker": "user", "text": "Fair concern. They've onboarded three teams our size this year in under two "
                                    "weeks, so I'd still choose them — could we agree on a two-week trial?"},
        {"speaker": "partner", "text": "Okay, that's helpful. Thanks."},
    ])
    first_attempt = MissionAttempt(
        id=new_id("att"), user_id=user.id, mission_id=mission.id, conversation_id=first.id, attempt_number=1,
        quick=False, status="complete", created_at=first_when,
        feedback=AttemptFeedback(
            assessable="yes", target_met="partly", headline="Your recommendation was there — it just arrived at the end.",
            where=_moment("so maybe we go with the new one?", "Your recommendation appears in your last sentence",
                          "conversation", first.id, 1),
            what_worked=["You named the real trade-off: cost versus familiarity."],
            one_change="Say \"I'd go with the new vendor\" in your first sentence, then give two reasons.",
            missing_evidence=None, comparison=None, issues=[],
        ).model_dump(mode="json"),
    )
    second_attempt = MissionAttempt(
        id=new_id("att"), user_id=user.id, mission_id=mission.id, conversation_id=second.id, attempt_number=2,
        quick=False, status="complete", created_at=second_when,
        feedback=AttemptFeedback(
            assessable="yes", target_met="yes",
            headline="Recommendation first, two reasons, then an invitation — that's the target.",
            where=_moment("I'd go with the new vendor.", "Recommendation in your first sentence", "conversation",
                          second.id, 1),
            what_worked=["Two reasons that matter to the decision: cost and security.",
                         "You answered the objection with a specific fact."],
            one_change="Pause for a beat after your recommendation so it lands.",
            missing_evidence=None,
            comparison=Comparison(
                previous_attempt_id=first_attempt.id,
                summary="This time your recommendation came first (first sentence instead of last), and both reasons "
                        "addressed the decision. You also answered the objection with a fact instead of a question.",
                changes=["Recommendation moved to the first sentence", "Answered the objection with evidence",
                         "Ended with a concrete next step"],
                note=COMPARISON_NOTE,
            ),
            issues=[],
        ).model_dump(mode="json"),
    )
    db.add_all([first_attempt, second_attempt])
    db.add(Reflection(id=new_id("rfl"), user_id=user.id, mission_id=mission.id, created_at=clock.at(0.63),
                      text="Tried leading with my recommendation in Monday's standup. Felt blunt at first, but people "
                           "actually responded faster.", went="well",
                      coach_reply="That's the hardest part — saying it first, out loud, with real people. Next time, "
                                  "add your two reasons right after, then pause and let them respond."))
    db.add(MissionProgress(user_id=user.id, mission_id=mission.id, status="completed",
                           takeaway="Recommendation first, then two reasons, then ask.", completed_at=clock.at(0.64)))
    if user.free_mission_id is None:
        user.free_mission_id = mission.id
    _log(db, user, "mission_attempt", mission.title, 2.5, first_attempt.id, first_when)
    _log(db, user, "mission_attempt", mission.title, 3.0, second_attempt.id, second_when)
    _log(db, user, "mission_completed", mission.title, 0, mission.id, clock.at(0.64))
    return mission.id


def _seed_spar(db: Session, user: User, clock: _Clock) -> str:
    cfo, date = PERSONAS["skeptical_cfo"], PERSONAS["first_date"]

    def persona_setup(p) -> ConversationSetup:
        return ConversationSetup(title=p.scenario, context=p.description, target_behavior=None, suggested_seconds=45,
                                 tips=["Say it the way you would in real life."], activity_id=None, mission_id=None,
                                 persona_id=p.id, difficulty=p.default_difficulty, quick=False)

    def partner(p) -> dict[str, Any]:
        return {"name": p.name, "role": p.title, "voice": p.voice, "symbol": p.symbol, "color_hex": p.color_hex}

    first_when, second_when = clock.at(0.7), clock.at(0.75)
    first = _conversation(db, user, kind="spar", partner=partner(cfo), setup=persona_setup(cfo), when=first_when,
                          persona_id=cfo.id, difficulty="brutal", max_user_turns=cfo.max_user_turns,
                          state={"character": cfo.character, "win_condition": cfo.win_condition,
                                 "outcome_label": "Budget approved"}, turns=[
        {"speaker": "partner", "text": cfo.opening, "momentum": 0.3},
        {"speaker": "user", "text": "I think it's, kind of, going to pay back pretty fast, because the team is really "
                                    "stretched."},
        {"speaker": "partner", "text": "Pretty fast isn't a number. Give me a number.", "momentum": 0.25,
         "whisper": "You're hedging — drop \"I think\" and lead with the payback."},
        {"speaker": "user", "text": "Seven months. We cut contractor spend by forty thousand a month."},
        {"speaker": "partner", "text": "Okay. And if it slips? What's my downside?", "momentum": 0.55,
         "whisper": "Good — now cap the risk."},
        {"speaker": "user", "text": "We stop after phase one. You'd risk a hundred and twenty thousand, not four hundred."},
        {"speaker": "partner", "text": "Alright. Phase one — and I want the numbers every month.", "momentum": 0.82,
         "whisper": "Ask clearly for the approval."},
    ])
    second = _conversation(db, user, kind="spar", partner=partner(date), setup=persona_setup(date), when=second_when,
                           persona_id=date.id, difficulty="kind", max_user_turns=date.max_user_turns,
                           state={"character": date.character, "win_condition": date.win_condition,
                                  "outcome_label": "Real connection"}, turns=[
        {"speaker": "partner", "text": date.opening, "momentum": 0.4},
        {"speaker": "user", "text": "Lucky guess, honestly! I picked it because of the plants. Are you a coffee person or "
                                    "a tea person?"},
        {"speaker": "partner", "text": "Tea, always. I'm a landscape architect, so I judge places by their plants too.",
         "momentum": 0.6, "whisper": "Nice — follow up on what Alex just shared."},
        {"speaker": "user", "text": "No way, a landscape architect? What's a project you're proud of?"},
        {"speaker": "partner", "text": "There's a tiny rooftop garden downtown I designed — it's my favorite secret spot.",
         "momentum": 0.78, "whisper": "Share something of your own now."},
        {"speaker": "user", "text": "I'd love to see it. Mine's less glamorous — I'm learning to bake sourdough and my "
                                    "neighbors are my test kitchen."},
        {"speaker": "partner", "text": "Okay, that's adorable. I'd volunteer as a taste tester.", "momentum": 0.86,
         "whisper": "Great balance of asking and sharing."},
    ])
    reports = [
        (first, SparReportOut(
            conversation_id=first.id, status="complete", title=cfo.scenario,
            outcome=SparOutcome(label="Budget approved",
                                detail="Marcus moved once you named the seven-month payback and capped the downside."),
            momentum=[MomentumPoint(turn_index=0, value=0.3, note=None),
                      MomentumPoint(turn_index=2, value=0.25, note="Hedging made the claim sound uncertain."),
                      MomentumPoint(turn_index=4, value=0.55, note="You named a specific payback period."),
                      MomentumPoint(turn_index=6, value=0.82, note="You capped the downside at phase one.")],
            moments=[RewriteMoment(dimension="persuasion",
                                   you_said="I think it's, kind of, going to pay back pretty fast",
                                   try_instead="It pays back in seven months. Here's how.",
                                   why="A number is easier to approve than a feeling.", source_type="conversation",
                                   source_id=first.id, turn_index=1, start_seconds=None, end_seconds=None,
                                   audio_url=None)],
            observations=[Observation(dimension="persuasion", note="Specific numbers and a capped downside turned a "
                                                                   "no into a yes."),
                          Observation(dimension="concision", note="After your first answer, every reply was one or "
                                                                  "two sentences.")],
            next_step="Open with the number next time: \"Seven-month payback — here's why.\"",
        )),
        (second, SparReportOut(
            conversation_id=second.id, status="complete", title=date.scenario,
            outcome=SparOutcome(label="Real connection",
                                detail="Alex opened up once you followed up on the rooftop garden."),
            momentum=[MomentumPoint(turn_index=0, value=0.4, note=None),
                      MomentumPoint(turn_index=2, value=0.6, note="You asked a question back."),
                      MomentumPoint(turn_index=4, value=0.78, note="You followed up on a specific detail."),
                      MomentumPoint(turn_index=6, value=0.86, note="You shared something real in return.")],
            moments=[RewriteMoment(dimension="warmth", you_said="Lucky guess, honestly!",
                                   try_instead="Lucky guess — I picked it for the plants. What made you choose it?",
                                   why="Giving a reason and asking back starts a real exchange sooner.",
                                   source_type="conversation", source_id=second.id, turn_index=1, start_seconds=None,
                                   end_seconds=None, audio_url=None)],
            observations=[Observation(dimension="listening", note="You followed up on a specific detail Alex shared."),
                          Observation(dimension="warmth", note="You balanced asking with sharing something real.")],
            next_step="Try a harder version: a busy person at a networking event.",
        )),
    ]
    for conv, report in reports:
        db.add(SparReport(conversation_id=conv.id, user_id=user.id, status="complete",
                          report=report.model_dump(mode="json"), created_at=conv.created_at))
        _log(db, user, "spar_session", conv.setup["title"], 4.0, conv.id, conv.created_at)
    return first.id


def _seed_event(db: Session, user: User, clock: _Clock) -> str:
    event = UpcomingEvent(
        id=new_id("evt"), user_id=user.id, title="Final-round interview at Northwind", kind="interview",
        date=(clock.now + timedelta(days=5)).date().isoformat(), notes="Product manager role. Panel of three.",
        created_at=clock.at(0.8),
        prep=[
            {"id": "prep_1", "title": "Warm-up: tell me about yourself",
             "scenario": "A friendly recruiter asks you to walk through your background in two minutes.",
             "partner_role": "Recruiter", "difficulty": "kind"},
            {"id": "prep_2", "title": "The product sense question",
             "scenario": "The hiring manager asks how you'd improve their onboarding flow, then pushes on your "
                         "assumptions.", "partner_role": "Hiring manager", "difficulty": "real"},
            {"id": "prep_3", "title": "The tough follow-up",
             "scenario": "A skeptical panelist challenges a decision from your last project and asks what you'd do "
                         "differently.", "partner_role": "Skeptical panelist", "difficulty": "brutal"},
        ],
    )
    db.add(event)
    return event.id


# ------------------------------------------------------------------ entry point


def seed(svc: AppServices, db: Session, user: User, pro: bool) -> DemoSeedResult:
    if pro:
        billing.dev_grant(svc.settings, user, "pro")
    existing = user.demo_seed
    if existing and db.get(Assessment, existing.get("assessment_id")) is not None:
        return DemoSeedResult.model_validate(existing)

    onboarding = users.onboarding(user)
    if not onboarding["completed"]:
        onboarding.update({"completed": True, "contexts_ranked": ["meetings", "interviews", "networking", "social"],
                           "ease_targets": ["concise", "persuading"], "goal_track": onboarding.get("goal_track")
                           or "business", "language": "en", "region": onboarding.get("region") or "US-CA"})
        user.onboarding = onboarding
        user.course_track = user.course_track or onboarding["goal_track"]
    if not user.analysis_consent_version:
        user.analysis_consent_version = ANALYSIS_VERSION
        user.analysis_consented_at = utcnow()

    clock = _Clock()
    assessment = _seed_assessment(db, user, clock)
    complete = _seed_complete_recording(db, user, clock)
    mission_id = _seed_mission(db, user, clock)
    spar_id = _seed_spar(db, user, clock)
    event_id = _seed_event(db, user, clock)
    pending = _seed_pending_recording(db, user, clock)
    db.flush()
    for key in ("first_conversation", "first_profile", "first_upload", "first_mission", "first_retry", "first_spar"):
        progress.award(db, user.id, key)
    if 6 >= users.practice_settings(user)["weekly_target"]:
        progress.award(db, user.id, "weekly_target", week_bounds(clock.now)[0].date().isoformat())
    result = DemoSeedResult(assessment_id=assessment.id, recording_needs_confirmation_id=pending.id,
                            recording_complete_id=complete.id, mission_id=mission_id, spar_conversation_id=spar_id,
                            event_id=event_id)
    user.demo_seed = result.model_dump()
    db.flush()
    return result
