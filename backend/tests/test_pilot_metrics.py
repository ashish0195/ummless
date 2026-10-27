from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db import Base, make_engine, make_session_factory
from app.models import (
    ActivityLog,
    DailyAttempt,
    DimensionEstimate,
    FeedbackReport,
    MissionAttempt,
    MissionProgress,
    Notification,
    Reflection,
    User,
)
from app.services import pilot_metrics

DAY = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def _attempt(id_: str, user: str, mission: str, number: int, status: str, when: datetime) -> MissionAttempt:
    return MissionAttempt(id=id_, user_id=user, mission_id=mission, conversation_id=f"cnv_{id_}",
                          attempt_number=number, status=status, created_at=when)


def _estimate(user: str, dimension: str, level: int, source: str, when: datetime) -> DimensionEstimate:
    return DimensionEstimate(user_id=user, dimension=dimension, status="assessed", level=level, confidence="moderate",
                             source_type="assessment", source_id=source, context_label="Test", assessed_at=when)


def test_pilot_metrics_report_engagement_and_learning_separately(settings) -> None:
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as db:
        db.add_all([
            User(id="usr_a", device_id="device-a", created_at=DAY),
            User(id="usr_b", device_id="device-b", created_at=DAY),
            User(id="usr_demo", device_id="device-demo", created_at=DAY, demo_seed={"assessment_id": "asm_demo"}),
        ])
        db.add_all([
            # usr_a: feedback, a voluntary retry, completes the mission, logs the real-life version,
            # and starts a different mission the next day.
            _attempt("a1", "usr_a", "business.m1.learn", 1, "complete", DAY),
            _attempt("a2", "usr_a", "business.m1.learn", 2, "complete", DAY + timedelta(minutes=10)),
            MissionProgress(user_id="usr_a", mission_id="business.m1.learn", completed_at=DAY + timedelta(minutes=20)),
            Reflection(id="rfl_a", user_id="usr_a", mission_id="business.m1.learn", text="It went well.",
                       created_at=DAY + timedelta(hours=5)),
            _attempt("a3", "usr_a", "business.m1.remix", 1, "processing", DAY + timedelta(days=1)),
            # usr_b: started, but the attempt never produced feedback.
            _attempt("b1", "usr_b", "business.m1.learn", 1, "failed", DAY),
            # Seeded demo data never counts.
            _attempt("d1", "usr_demo", "business.m1.learn", 1, "complete", DAY),
            _estimate("usr_demo", "clarity", 1, "asm_demo", DAY),
            _estimate("usr_demo", "clarity", 5, "rec_demo", DAY + timedelta(days=2)),
        ])
        db.add_all([
            # Clarity was assessed in two different conversations; warmth only once, so it isn't compared.
            _estimate("usr_a", "clarity", 2, "asm_a", DAY),
            _estimate("usr_a", "clarity", 3, "rec_a", DAY + timedelta(days=3)),
            _estimate("usr_a", "warmth", 4, "asm_a", DAY),
            _estimate("usr_b", "concision", 3, "asm_b", DAY),
            _estimate("usr_b", "concision", 3, "rec_b", DAY + timedelta(days=4)),
            FeedbackReport(id="fbr_a", user_id="usr_a", target_type="dimension_result", target_id="asm_a",
                           dimension="clarity", reason="misheard"),
        ])
        db.commit()

        report = pilot_metrics.compute(db)
        assert report["people"] == 2
        engagement = report["engagement"]
        assert (engagement["first_task_completion"]["numerator"],
                engagement["first_task_completion"]["denominator"]) == (1, 2)
        assert engagement["first_task_completion"]["rate"] == 0.5
        assert engagement["voluntary_retries"]["rate"] == 1.0
        assert engagement["return_for_next_mission"]["rate"] == 1.0
        assert engagement["real_life_application"]["rate"] == 1.0

        learning = report["learning"]["improvement_on_fresh_scenario"]
        assert (learning["skills_compared"], learning["higher"], learning["same"], learning["lower"]) == (2, 1, 1, 0)
        assert report["calibration"] == {"feedback_reports": 1, "by_reason": {"misheard": 1},
                                         "by_target": {"dimension_result": 1}}

        later = pilot_metrics.compute(db, since=DAY + timedelta(days=1))
        assert later["people"] == 0
        assert later["engagement"]["first_task_completion"]["rate"] is None


def test_habit_metrics_daily_rep_completion_and_push_to_session(settings) -> None:
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)

    def rep(id_: str, user: str, day: str, number: int, status: str, assessable: str | None) -> DailyAttempt:
        feedback = {"assessable": assessable} if assessable else None
        return DailyAttempt(id=id_, user_id=user, date=day, prompt_id="explain.job_to_kid", conversation_id=f"c_{id_}",
                            attempt_number=number, status=status, feedback=feedback, created_at=DAY)

    def note(id_: str, user: str, state: str, opened: datetime | None) -> Notification:
        return Notification(id=id_, user_id=user, category="nudge", title="t", body="b", deep_link="comlogue://daily",
                            dedupe_key=id_, created_at=DAY, deliver_after=DAY, push_state=state, opened_at=opened)

    with make_session_factory(engine)() as db:
        db.add_all([User(id="usr_a", device_id="device-a", created_at=DAY),
                    User(id="usr_b", device_id="device-b", created_at=DAY),
                    User(id="usr_demo", device_id="device-demo", created_at=DAY, demo_seed={"assessment_id": "x"})])
        db.add_all([
            # usr_a: day 1 not assessable, then a retry that worked (1 completed day); day 2 failed.
            rep("r1", "usr_a", "2026-11-02", 1, "complete", "no"),
            rep("r2", "usr_a", "2026-11-02", 2, "complete", "partly"),
            rep("r3", "usr_a", "2026-11-03", 1, "failed", None),
            # usr_b: one completed day.
            rep("r4", "usr_b", "2026-11-02", 1, "complete", "yes"),
            rep("r5", "usr_demo", "2026-11-02", 1, "complete", "yes"),
            # Pushes: three delivered, two tapped; one inbox tap (never pushed). A session follows one tap within
            # two hours, another tap is followed only after three hours.
            note("n1", "usr_a", "sent", DAY + timedelta(hours=1)),
            note("n2", "usr_a", "sent", None),
            note("n3", "usr_b", "sent", DAY + timedelta(hours=2)),
            note("n4", "usr_b", "skipped", DAY + timedelta(hours=9)),
            note("n5", "usr_demo", "sent", DAY),
            ActivityLog(user_id="usr_a", type="daily_rep", title="Rep", minutes=1,
                        created_at=DAY + timedelta(hours=1, minutes=20)),
            ActivityLog(user_id="usr_b", type="daily_rep", title="Rep", minutes=1, created_at=DAY + timedelta(hours=5)),
            ActivityLog(user_id="usr_b", type="mission_completed", title="Not a session", minutes=0,
                        created_at=DAY + timedelta(hours=9, minutes=5)),
        ])
        db.commit()
        engagement = pilot_metrics.compute(db)["engagement"]
        completion = engagement["daily_rep_completion"]
        assert (completion["numerator"], completion["denominator"], completion["rate"]) == (2, 3, 0.667)
        assert (engagement["push_open_rate"]["numerator"], engagement["push_open_rate"]["denominator"]) == (2, 3)
        conversion = engagement["push_to_session"]
        assert (conversion["numerator"], conversion["denominator"]) == (1, 3)
        assert "learning" in pilot_metrics.compute(db)  # engagement and learning stay separate
