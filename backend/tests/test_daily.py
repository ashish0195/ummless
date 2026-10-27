"""Daily rep: deterministic, market-aware selection, the upcoming window, shuffling, the attempt flow with feedback
and comparison, and once-a-day session counting."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.domain.content.daily_prompts import DAILY_PROMPTS
from app.domain.market_content import DAILY_PROMPTS_BY_ID, daily_prompts_for
from app.models import ActivityLog, Notification, User
from app.services import daily
from app.timeutil import local_date, utcnow
from tests.helpers import post_turn, signup, speech_file

SEED_PROMPTS = ("explain.job_to_kid", "introduce.placement_hr", "persuade.weekend_plan")


def _svc(client):
    return client.app.state.services


def _today(client, headers) -> date:
    return date.fromisoformat(client.get("/v1/daily", headers=headers).json()["date"])


def _rep_attempt(client, headers, audio_dir, *, name: str, daily_date: str | None = None) -> dict:
    body = {"kind": "daily"} | ({"daily_date": daily_date} if daily_date else {})
    created = client.post("/v1/conversations", headers=headers, json=body)
    assert created.status_code == 200, created.text
    conv = created.json()
    path = speech_file(audio_dir, f"{name}.m4a", seconds=14)
    turn = post_turn(client, headers, conv["id"], path)
    assert turn.status_code == 200, turn.text
    finished = client.post(f"/v1/conversations/{conv['id']}/finish", headers=headers)
    assert finished.status_code == 200, finished.text
    return {"conversation": conv, "turn": turn.json(), "finish": finished.json()}


def test_seed_prompts_exist_with_their_markets():
    for prompt_id in SEED_PROMPTS:
        assert prompt_id in DAILY_PROMPTS_BY_ID
    assert DAILY_PROMPTS_BY_ID["introduce.placement_hr"].markets == ("in",)
    assert all("in" in p.markets for p in daily_prompts_for("in"))
    assert "introduce.placement_hr" not in {p.id for p in daily_prompts_for("us")}
    assert len({p.id for p in DAILY_PROMPTS}) == len(DAILY_PROMPTS)


def test_todays_rep_shape_and_stability(client):
    headers = signup(client)
    rep = client.get("/v1/daily", headers=headers).json()
    assert set(rep) == {"date", "prompt_id", "title", "prompt", "kind", "dimension", "target_behavior", "tips",
                        "suggested_seconds", "example", "can_shuffle", "completed", "attempts"}
    assert rep["prompt_id"] in DAILY_PROMPTS_BY_ID and len(rep["tips"]) == 2
    assert rep["completed"] is False and rep["attempts"] == [] and rep["can_shuffle"] is True
    assert 30 <= rep["suggested_seconds"] <= 90
    assert client.get("/v1/daily", headers=headers).json()["prompt_id"] == rep["prompt_id"]
    assert client.get(f"/v1/daily/{rep['date']}", headers=headers).json()["prompt_id"] == rep["prompt_id"]


def test_selection_is_deterministic_per_user_and_date(client):
    headers = signup(client)
    user_id = client.get("/v1/me", headers=headers).json()["user_id"]
    with _svc(client).session_factory() as db:
        user = db.get(User, user_id)
        day = date(2026, 11, 4)
        picks = {daily._choose(user, day, market="us", focus="clarity", track="business", rep_count=3,
                               recent=set(), exclude=set()).id for _ in range(5)}
        assert len(picks) == 1
        weekend = [daily._choose(user, day + timedelta(days=offset), market="us", focus=None, track="business",
                                 rep_count=3, recent=set(), exclude=set()) for offset in range(3, 5)]
        assert all(p.id in DAILY_PROMPTS_BY_ID for p in weekend)


def test_upcoming_is_stable_and_has_no_repeats(client):
    headers = signup(client)
    upcoming = client.get("/v1/daily/upcoming?days=14", headers=headers).json()["items"]
    today = _today(client, headers)
    assert [item["date"] for item in upcoming] == [(today + timedelta(days=i)).isoformat() for i in range(14)]
    assert upcoming[0]["prompt_id"] == client.get("/v1/daily", headers=headers).json()["prompt_id"]
    assert len({item["prompt_id"] for item in upcoming}) == 14
    assert set(upcoming[0]) == {"date", "prompt_id", "title", "prompt", "dimension"}
    again = client.get("/v1/daily/upcoming", headers=headers).json()["items"]
    assert again == upcoming[:7]
    for bad in (0, 15):
        response = client.get(f"/v1/daily/upcoming?days={bad}", headers=headers)
        assert response.status_code == 422, response.text


def test_prompts_follow_the_market(client):
    india = signup(client)
    client.patch("/v1/me", headers=india, json={"onboarding": {"region": "IN-MH"}})
    us = signup(client)
    india_ids = {i["prompt_id"] for i in client.get("/v1/daily/upcoming?days=14", headers=india).json()["items"]}
    us_ids = {i["prompt_id"] for i in client.get("/v1/daily/upcoming?days=14", headers=us).json()["items"]}
    assert all("in" in DAILY_PROMPTS_BY_ID[pid].markets for pid in india_ids)
    assert all("us" in DAILY_PROMPTS_BY_ID[pid].markets for pid in us_ids)


def test_the_date_follows_the_users_timezone(client):
    headers = signup(client)
    client.post("/v1/devices", headers=headers, json={"apns_token": None, "authorization": "denied",
                                                      "timezone": "Asia/Kolkata"})
    assert _today(client, headers) == local_date(utcnow(), "Asia/Kolkata")
    client.post("/v1/devices", headers=headers, json={"apns_token": None, "authorization": "denied",
                                                      "timezone": "America/Los_Angeles"})
    assert _today(client, headers) == local_date(utcnow(), "America/Los_Angeles")


def test_date_range_and_unassigned_past_days(client):
    headers = signup(client)
    today = _today(client, headers)
    assert client.get(f"/v1/daily/{(today + timedelta(days=14)).isoformat()}", headers=headers).status_code == 200
    for offset in (-31, 15):
        response = client.get(f"/v1/daily/{(today + timedelta(days=offset)).isoformat()}", headers=headers)
        assert response.status_code == 404
    # Past days are never assigned after the fact.
    assert client.get(f"/v1/daily/{(today - timedelta(days=3)).isoformat()}", headers=headers).status_code == 404
    assert client.get("/v1/daily/2026-13-01", headers=headers).status_code == 422


def test_shuffle_once_before_the_first_try(client, audio_dir):
    headers = signup(client)
    before = client.get("/v1/daily", headers=headers).json()
    shuffled = client.post("/v1/daily/shuffle", headers=headers)
    assert shuffled.status_code == 200, shuffled.text
    after = shuffled.json()
    assert after["prompt_id"] != before["prompt_id"] and after["can_shuffle"] is False
    assert client.get("/v1/daily", headers=headers).json()["prompt_id"] == after["prompt_id"]
    again = client.post("/v1/daily/shuffle", headers=headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "conflict"

    other = signup(client)
    _rep_attempt(client, other, audio_dir, name="before_shuffle")
    assert client.get("/v1/daily", headers=other).json()["can_shuffle"] is False
    assert client.post("/v1/daily/shuffle", headers=other).status_code == 409


def test_daily_rep_flow_feedback_comparison_and_one_session_per_day(client, audio_dir):
    headers = signup(client)
    rep = client.get("/v1/daily", headers=headers).json()
    first = _rep_attempt(client, headers, audio_dir, name="rep1")
    conv = first["conversation"]
    assert conv["kind"] == "daily" and conv["max_user_turns"] == 1 and conv["participants"] == []
    assert conv["turns"][0]["speaker"] == "partner" and conv["turns"][0]["text"] == rep["prompt"]
    assert conv["partner"]["name"] == "Maya" and conv["setup"]["target_behavior"] == rep["target_behavior"]
    turn = first["turn"]
    assert turn["done"] is True and turn["conversation"]["awaiting"] == "none"
    assert len(turn["partner_turns"]) == 1 and turn["partner_turn"] == turn["partner_turns"][0]
    ref = first["finish"]["result_ref"]
    assert ref["type"] == "daily_attempt" and ref["id"].startswith("att_")
    # Finishing again is idempotent.
    again = client.post(f"/v1/conversations/{conv['id']}/finish", headers=headers).json()
    assert again["result_ref"] == ref

    after_first = client.get(f"/v1/daily/{rep['date']}", headers=headers).json()
    assert after_first["completed"] is True and len(after_first["attempts"]) == 1
    attempt = after_first["attempts"][0]
    assert attempt["id"] == ref["id"] and attempt["status"] == "complete" and attempt["attempt_number"] == 1
    assert attempt["feedback"]["assessable"] in ("yes", "partly") and attempt["feedback"]["comparison"] is None

    _rep_attempt(client, headers, audio_dir, name="rep2")
    after_second = client.get("/v1/daily", headers=headers).json()
    assert [a["attempt_number"] for a in after_second["attempts"]] == [1, 2]
    comparison = after_second["attempts"][1]["feedback"]["comparison"]
    assert comparison is not None and comparison["previous_attempt_id"] == ref["id"]

    practice = client.get("/v1/progress", headers=headers).json()["practice"]
    assert practice["reps"] == 1 and practice["this_week"]["sessions"] == 1
    assert "first_rep" in {m["id"] for m in client.get("/v1/progress", headers=headers).json()["milestones"]}
    user_id = client.get("/v1/me", headers=headers).json()["user_id"]
    with _svc(client).session_factory() as db:
        logs = list(db.scalars(select(ActivityLog).where(ActivityLog.user_id == user_id,
                                                         ActivityLog.type == "daily_rep")))
        assert len(logs) == 1 and logs[0].ref_id == f"daily:{rep['date']}"
        # They were in the app when feedback landed: no "feedback ready" notification.
        assert db.scalar(select(Notification.id).where(Notification.user_id == user_id,
                                                       Notification.category == "results")) is None


def test_yesterdays_rep_is_allowed_older_ones_are_not(client, audio_dir):
    headers = signup(client)
    today = _today(client, headers)
    yesterday = (today - timedelta(days=1)).isoformat()
    attempt = _rep_attempt(client, headers, audio_dir, name="late", daily_date=yesterday)
    assert attempt["conversation"]["kind"] == "daily"
    assert client.get(f"/v1/daily/{yesterday}", headers=headers).json()["completed"] is True
    old = client.post("/v1/conversations", headers=headers,
                      json={"kind": "daily", "daily_date": (today - timedelta(days=2)).isoformat()})
    assert old.status_code == 409


def test_daily_reps_are_free_and_need_consent(client, audio_dir):
    no_consent = signup(client, consent=False)
    assert client.post("/v1/conversations", headers=no_consent, json={"kind": "daily"}).status_code == 403
    free = signup(client)
    for index in range(3):  # unlimited retries on the free tier
        _rep_attempt(client, free, audio_dir, name=f"free{index}")
    assert len(client.get("/v1/daily", headers=free).json()["attempts"]) == 3
