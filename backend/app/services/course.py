"""Course plan, missions, attempt feedback and reflections.

The plan follows observed needs when evidence exists ("Tailored to your profile") and the user's goal
otherwise ("Based on your goal"). Free tier: the baseline, one practice mission and the full preview.
Mission feedback never changes the communication web; practice completion is tracked separately.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.types import AttemptRequest, ReflectionRequest
from ..core import AppServices
from ..domain.activities import ACTIVITIES, GAP_ACTIVITY, GAP_TITLES
from ..domain.course import (
    MISSIONS,
    MODULES,
    MODULES_BY_TRACK,
    TRACKS,
    MissionDef,
    ModuleDef,
)
from ..domain.dimensions import DIMENSIONS
from ..domain.issues import issue
from ..domain.market_content import mission_for_market, module_for_market
from ..errors import AIUnavailableError, not_found, subscription_required
from ..ids import new_id
from ..models import (
    Conversation,
    DailyAttempt,
    MissionAttempt,
    MissionProgress,
    Reflection,
    Turn,
    User,
)
from ..schemas import (
    AttemptFeedback,
    Comparison,
    Course,
    CourseModule,
    EvidenceMoment,
    GapTask,
    Issue,
    MissionAttemptOut,
    MissionExample,
    MissionOut,
    MissionSummary,
    QuickOption,
    RealLife,
    ReflectionCreate,
    ReflectionOut,
    TodayPlan,
    TrackInfo,
)
from ..timeutil import iso_required, utcnow
from . import conversations, notifications, progress, tts, users
from . import media as media_service
from . import profile as profile_service
from .analysis import find_unit

log = logging.getLogger("comlogue.course")

COMPARISON_NOTE = "A shorter answer isn't automatically a better one — we compared both attempts against the same target."
MISSION_ORDER = ("learn_and_try", "remix", "real_life", "weekly_reveal")


def track_info(track_id: str) -> TrackInfo:
    data = TRACKS[track_id]
    return TrackInfo(id=track_id, title=data["title"], subtitle=data["subtitle"], symbol=data["symbol"])


def _completed(db: Session, user: User) -> dict[str, MissionProgress]:
    return {p.mission_id: p for p in db.scalars(select(MissionProgress).where(MissionProgress.user_id == user.id))}


def free_mission_id(user: User, focus_module: ModuleDef) -> str:
    return user.free_mission_id or focus_module.mission("learn_and_try").id


def _ordered_modules(track_id: str, estimates: dict) -> list[ModuleDef]:
    modules = MODULES_BY_TRACK[track_id]
    if not estimates:
        return list(modules)

    def priority(module: ModuleDef) -> tuple[int, int, int]:
        row = estimates.get(module.dimension)
        if row is not None and row.level <= 2:
            return (0, row.level, module.index)
        return (1, 0, module.index)

    return sorted(modules, key=priority)


def mission_status(user: User, mission: MissionDef, completed: dict, free_id: str, pro: bool) -> tuple[str, str | None]:
    if mission.id in completed:
        return "completed", None
    if not pro and mission.id != free_id:
        return "locked", "subscribe"
    return "available", None


def build_course(svc: AppServices, db: Session, user: User) -> Course:
    track_id = users.goal_track(user)
    market = users.market(user)
    estimates = profile_service.current_estimates(db, user)
    ordered = _ordered_modules(track_id, estimates)
    completed = _completed(db, user)
    pro = users.is_pro(user)

    def module_done(module: ModuleDef) -> bool:
        return all(m.id in completed for m in module.missions)

    focus = MODULES.get(user.course_focus_module_id or "")
    if focus is None or focus.track_id != track_id:
        focus = next((m for m in ordered if not module_done(m)), ordered[0])
    free_id = free_mission_id(user, focus)

    modules_out: list[CourseModule] = []
    for index, module in enumerate(ordered, start=1):
        missions = []
        for mission in module.missions:
            status, reason = mission_status(user, mission, completed, free_id, pro)
            missions.append(MissionSummary(id=mission.id, type=mission.type,
                                           title=mission_for_market(mission, market).title,
                                           minutes=mission.minutes, status=status, locked_reason=reason))
        done = sum(1 for m in module.missions if m.id in completed)
        status = "completed" if done == len(module.missions) else ("current" if module.id == focus.id else "available")
        modules_out.append(CourseModule(
            id=module.id, index=index, title=module.title, dimension=module.dimension,
            target_behavior=module.target_behavior, summary=module_for_market(module, market).summary, status=status,
            completed_missions=done, missions=missions,
        ))

    if estimates:
        basis, label = "profile", "Tailored to your profile"
        names = ", ".join(DIMENSIONS[d].title.lower() for d in estimates)
        explainer = (f"Ordered using what we've seen so far ({names}) plus your goal. "
                     "You can change the focus anytime.")
    else:
        basis, label = "goal", "Based on your goal"
        explainer = ("We don't have enough evidence about how you communicate yet, so this plan follows your goal. "
                     "It will adapt once a conversation gives us evidence.")

    gap_tasks: list[GapTask] = []
    if estimates:
        track_dims = [m.dimension for m in MODULES_BY_TRACK[track_id]]
        missing = [d for d in DIMENSIONS if d not in estimates]
        missing.sort(key=lambda d: (0 if d in track_dims else 1, list(DIMENSIONS).index(d)))
        seen: set[str] = set()
        for dim in missing:
            activity_id = GAP_ACTIVITY[dim]
            if activity_id in seen or len(gap_tasks) >= 3:
                continue
            seen.add(activity_id)
            gap_tasks.append(GapTask(dimension=dim, activity_id=activity_id, title=GAP_TITLES[dim],
                                     minutes=ACTIVITIES[activity_id].minutes,
                                     reason=f"Not enough evidence yet for {DIMENSIONS[dim].title.lower()}."))

    today = None
    focus_out = next(m for m in modules_out if m.id == focus.id)
    next_mission = next((m for m in focus_out.missions if m.status != "completed"), None)
    if next_mission is not None:
        if next_mission.status == "locked" and not pro:
            free_summary = next((m for mod in modules_out for m in mod.missions
                                 if m.id == free_id and m.status == "available"), None)
            next_mission = free_summary or next_mission
        quick = None
        if next_mission.type in ("learn_and_try", "remix") and next_mission.status == "available":
            quick = QuickOption(mission_id=next_mission.id, title="Two-minute version", minutes=2)
        module_title = MODULES[MISSIONS[next_mission.id].module_id].title
        today = TodayPlan(mission=next_mission, module_title=module_title, quick=quick)

    return Course(track=track_info(track_id), basis=basis, basis_label=label, basis_explainer=explainer,
                  focus_module_id=focus.id, modules=modules_out, gap_tasks=gap_tasks, today=today, is_pro=pro,
                  free_mission_id=None if pro else free_id)


def set_track(user: User, track_id: str) -> None:
    user.course_track = track_id
    user.course_focus_module_id = None
    data = users.onboarding(user)
    data["goal_track"] = track_id
    user.onboarding = data


def set_focus(user: User, module_id: str) -> None:
    module = MODULES.get(module_id)
    if module is None:
        raise not_found("Module")
    user.course_track = module.track_id
    user.course_focus_module_id = module_id


# ------------------------------------------------------------------ missions


def _mission(mission_id: str) -> MissionDef:
    mission = MISSIONS.get(mission_id)
    if mission is None:
        raise not_found("Mission")
    return mission


def ensure_unlocked(db: Session, user: User, mission: MissionDef) -> None:
    """Free users get exactly one practice mission; starting it locks in the choice."""
    if users.is_pro(user):
        return
    course = build_course_free_id(db, user)
    if mission.id != course:
        raise subscription_required("This mission is part of Comlogue Pro. Your free practice mission is waiting.")
    if user.free_mission_id is None:
        user.free_mission_id = mission.id


def focus_module(db: Session, user: User) -> ModuleDef:
    """The module the course is focused on (the user's choice, else the first unfinished one in plan order)."""
    track_id = users.goal_track(user)
    focus = MODULES.get(user.course_focus_module_id or "")
    if focus is not None and focus.track_id == track_id:
        return focus
    ordered = _ordered_modules(track_id, profile_service.current_estimates(db, user))
    completed = _completed(db, user)
    return next((m for m in ordered if not all(x.id in completed for x in m.missions)), ordered[0])


def build_course_free_id(db: Session, user: User) -> str:
    return free_mission_id(user, focus_module(db, user))


def _feedback_out(svc: AppServices, attempt: MissionAttempt) -> MissionAttemptOut:
    feedback = None
    if attempt.feedback:
        feedback = AttemptFeedback.model_validate(media_service.resolve_media(svc, attempt.feedback))
    return MissionAttemptOut(id=attempt.id, conversation_id=attempt.conversation_id,
                             attempt_number=attempt.attempt_number, quick=attempt.quick, status=attempt.status,
                             feedback=feedback, created_at=iso_required(attempt.created_at))


EXAMPLE_TTS = {
    "in": "Voice: warm, natural, confident colleague with a neutral Indian English accent. Pace: relaxed.",
}
EXAMPLE_TTS_DEFAULT = "Voice: warm, natural, confident colleague. Pace: relaxed."


def mission_out(svc: AppServices, db: Session, user: User, mission_id: str) -> MissionOut:
    market = users.market(user)
    mission = mission_for_market(_mission(mission_id), market)
    module = module_for_market(MODULES[mission.module_id], market)
    completed = _completed(db, user)
    free_id = build_course_free_id(db, user)
    status, reason = mission_status(user, mission, completed, free_id, users.is_pro(user))
    attempts = list(db.scalars(select(MissionAttempt).where(
        MissionAttempt.user_id == user.id, MissionAttempt.mission_id == mission_id).order_by(MissionAttempt.attempt_number)))
    reflections = list(db.scalars(select(Reflection).where(
        Reflection.user_id == user.id, Reflection.mission_id == mission_id).order_by(Reflection.created_at)))
    example_text = module.example_text.strip('"“”')  # the app adds its own quotation marks
    example_media = tts.speak(svc, db, example_text, "marin", EXAMPLE_TTS.get(market, EXAMPLE_TTS_DEFAULT))
    real_life = None
    if mission.type == "real_life":
        real_life = RealLife(prompt=mission.real_life_prompt or mission.context,
                             ai_alternative_title=mission.ai_alternative_title or "Practice with AI instead",
                             reflection_questions=list(mission.reflection_questions))
        notifications.note_mission_opened(db, user, mission_id)
    progress_row = completed.get(mission_id)
    return MissionOut(
        id=mission.id, module_id=module.id, track_id=module.track_id, type=mission.type, title=mission.title,
        dimension=module.dimension, minutes=mission.minutes, context=mission.context,
        target_behavior=module.target_behavior, why_it_matters=module.why_it_matters,
        example=MissionExample(text=example_text, audio_url=media_service.url_for(svc, example_media),
                               explanation=module.example_explanation),
        steps=list(mission.steps), suggested_seconds=mission.suggested_seconds, real_life=real_life,
        attempts=[_feedback_out(svc, a) for a in attempts],
        reflections=[ReflectionOut(id=r.id, text=r.text, went=r.went, coach_reply=r.coach_reply,
                                   created_at=iso_required(r.created_at)) for r in reflections],
        status=status, locked_reason=reason, takeaway=progress_row.takeaway if progress_row else None,
    )


def complete_mission(db: Session, user: User, mission_id: str, takeaway: str | None) -> None:
    mission = mission_for_market(_mission(mission_id), users.market(user))
    ensure_unlocked(db, user, mission)
    row = db.scalar(select(MissionProgress).where(MissionProgress.user_id == user.id,
                                                  MissionProgress.mission_id == mission_id))
    if row is None:
        row = MissionProgress(user_id=user.id, mission_id=mission_id, status="completed", takeaway=takeaway)
        db.add(row)
        progress.log_activity(db, user.id, "mission_completed", mission.title, 0, mission_id)
        if mission.type == "real_life":
            progress.log_activity(db, user.id, "real_life", mission.title, mission.minutes, mission_id)
            progress.award(db, user.id, "first_real_life")
        progress.award(db, user.id, "first_mission")
    elif takeaway is not None:
        row.takeaway = takeaway
    db.flush()


def add_reflection(svc: AppServices, db: Session, user: User, mission_id: str, body: ReflectionCreate) -> ReflectionOut:
    mission = mission_for_market(_mission(mission_id), users.market(user))
    module = MODULES[mission.module_id]
    try:
        reply = svc.ai.reflection_reply(ReflectionRequest(
            language=users.language(user), mission_title=mission.title, target_behavior=module.target_behavior,
            real_life_prompt=mission.real_life_prompt or mission.context, text=body.text, went=body.went,
        )).reply
    except AIUnavailableError:
        reply = "Thanks for reflecting — noticing what happened is how the next try gets easier."
    reflection = Reflection(id=new_id("rfl"), user_id=user.id, mission_id=mission_id, text=body.text, went=body.went,
                            coach_reply=reply)
    db.add(reflection)
    if mission.type == "real_life":
        progress.award(db, user.id, "first_real_life")
    db.flush()
    return ReflectionOut(id=reflection.id, text=reflection.text, went=reflection.went,
                         coach_reply=reflection.coach_reply, created_at=iso_required(reflection.created_at or utcnow()))


# ------------------------------------------------------------------ attempt feedback job


def _turn_issues(turns: list[Turn]) -> list[Issue]:
    seen: dict[str, Issue] = {}
    for turn in turns:
        if turn.speaker != "user":
            continue
        for raw in (turn.quality or {}).get("issues", []):
            item = Issue.model_validate(raw)
            seen.setdefault(item.code, item)
    return list(seen.values())


def judge_attempt(svc: AppServices, db: Session, user: User, conv: Conversation, *, title: str,
                  target_behavior: str, quick: bool, previous: MissionAttempt | DailyAttempt | None) -> AttemptFeedback:
    """Feedback on one attempt at one target behavior (missions and daily reps).

    Raises AIUnavailableError when the model call fails after fallbacks.
    """
    turns = conversations.turns_of(db, conv)
    units = conversations.units_for(conv, turns)
    issues = _turn_issues(turns)
    user_units = [u for u in units if u.usable_user]
    if not user_units:
        return AttemptFeedback(
            assessable="no", target_met="unclear", headline="We couldn't hear enough of your answer this time.",
            where=None, what_worked=[], one_change=None,
            missing_evidence="This was about the audio or a very short answer — not your skill. Try again "
            "somewhere quieter.",
            comparison=None, issues=issues or [issue("too_short")],
        )
    previous_units = None
    previous_headline = None
    if previous is not None and (previous.feedback or {}).get("assessable") != "no":
        prev_conv = db.get(Conversation, previous.conversation_id)
        if prev_conv is not None:
            previous_units = conversations.units_for(prev_conv, conversations.turns_of(db, prev_conv), "P")
            previous_headline = (previous.feedback or {}).get("headline")
    judgement = svc.ai.attempt_feedback(AttemptRequest(
        language=conv.language, mission_title=title, target_behavior=target_behavior,
        context=conv.setup.get("context", ""), partner_name=conv.partner.get("name", "Partner"),
        units=units, previous_units=previous_units, previous_headline=previous_headline, quick=quick,
    ))
    where = None
    if judgement.where_segment_id:
        unit = find_unit({u.uid: u for u in units}, user_units, judgement.where_segment_id,
                          judgement.where_quote or "")
        if unit is not None:
            clip_id = media_service.clip(svc, db, user_id=user.id, source_media_id=unit.media_id,
                                         start=unit.start, end=unit.end)
            where = EvidenceMoment(quote=judgement.where_quote or " ".join(unit.text.split()[:25]),
                                   note=judgement.where_note, source_type="conversation", source_id=conv.id,
                                   turn_index=unit.turn_index, start_seconds=unit.start, end_seconds=unit.end,
                                   audio_url=media_service.media_ref(clip_id))
    assessable = judgement.assessable
    if any(u.role == "user" and u.excluded for u in units) and assessable == "yes":
        assessable = "partly"
    comparison = None
    if previous_units is not None and previous is not None and judgement.comparison_summary:
        comparison = Comparison(previous_attempt_id=previous.id, summary=judgement.comparison_summary,
                                changes=judgement.comparison_changes[:3], note=COMPARISON_NOTE)
    target_met = judgement.target_met if assessable != "no" else "unclear"
    return AttemptFeedback(
        assessable=assessable, target_met=target_met, headline=judgement.headline, where=where,
        what_worked=judgement.what_worked[:2], one_change=judgement.one_change,
        missing_evidence=judgement.missing_evidence, comparison=comparison, issues=issues,
    )


def run_feedback_job(svc: AppServices, attempt_id: str) -> None:
    db = svc.session_factory()
    try:
        attempt = db.get(MissionAttempt, attempt_id)
        if attempt is None or attempt.status != "processing":
            return
        conv = db.get(Conversation, attempt.conversation_id)
        user = db.get(User, attempt.user_id)
        if conv is None or user is None:
            return
        mission = mission_for_market(MISSIONS[attempt.mission_id], users.market(user))
        module = MODULES[mission.module_id]
        previous = db.scalar(select(MissionAttempt).where(
            MissionAttempt.user_id == user.id, MissionAttempt.mission_id == attempt.mission_id,
            MissionAttempt.attempt_number < attempt.attempt_number, MissionAttempt.status == "complete",
        ).order_by(MissionAttempt.attempt_number.desc()))
        try:
            feedback = judge_attempt(svc, db, user, conv, title=mission.title, target_behavior=module.target_behavior,
                                     quick=attempt.quick, previous=previous)
        except AIUnavailableError as exc:
            log.warning("Attempt feedback failed: %s", exc)
            attempt.status = "failed"
            db.commit()
            return
        attempt.feedback = feedback.model_dump(mode="json")
        attempt.status = "complete"
        if feedback.assessable != "no":
            if attempt.attempt_number >= 2:
                progress.award(db, user.id, "first_retry")
            if mission.type == "remix" and feedback.target_met == "yes":
                progress.award(db, user.id, "new_scenario")
        db.commit()
        notifications.feedback_ready(svc, db, user.id, attempt_id=attempt.id,
                                     title=f"Feedback on “{mission.title}” is ready",
                                     deep_link=f"comlogue://mission/{mission.id}")
    except Exception:
        db.rollback()
        attempt = db.get(MissionAttempt, attempt_id)
        if attempt is not None and attempt.status == "processing":
            attempt.status = "failed"
            db.commit()
        raise
    finally:
        db.close()


def module_for(mission_id: str) -> ModuleDef:
    return MODULES[_mission(mission_id).module_id]


def mission_order_key(mission: MissionDef) -> int:
    return MISSION_ORDER.index(mission.type)
