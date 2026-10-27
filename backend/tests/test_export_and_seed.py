"""Data export, account deletion of v2 data, and the v2 demo seed (both markets)."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app.domain import market_content
from app.models import DailyAssignment, DailyAttempt, Device, MissionOpen, Notification
from app.push import RecordingSender
from tests.helpers import post_turn, signup, speech_file

TOKEN = "cd" * 32


def _media_urls(value, path="$"):
    """Every non-null `*_url` value in a JSON document."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key.endswith("_url") and item is not None:
                yield f"{path}.{key}"
            yield from _media_urls(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _media_urls(item, f"{path}[{index}]")


def _daily_attempt(client, headers, audio_dir) -> None:
    conv = client.post("/v1/conversations", headers=headers, json={"kind": "daily"}).json()
    assert post_turn(client, headers, conv["id"], speech_file(audio_dir, "rep.m4a", seconds=12)).status_code == 200
    assert client.post(f"/v1/conversations/{conv['id']}/finish", headers=headers).status_code == 200


def test_export_contains_everything_but_audio(client, audio_dir):
    client.app.state.services.push = RecordingSender()
    headers = signup(client)
    client.post("/v1/devices", headers=headers, json={"apns_token": TOKEN, "authorization": "authorized",
                                                      "timezone": "Asia/Kolkata", "push_environment": "sandbox"})
    _daily_attempt(client, headers, audio_dir)
    client.post("/v1/events", headers=headers, json={"title": "HR round", "kind": "placement", "time": "11:00",
                                                     "date": (date.today() + timedelta(days=2)).isoformat()})
    client.post("/v1/notifications/test", headers=headers)
    client.get("/v1/missions/business.m1.real", headers=headers)

    response = client.get("/v1/me/export", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["content-disposition"] == 'attachment; filename="comlogue-export.json"'
    data = json.loads(response.content)
    assert {"export_version", "exported_at", "account", "voice_reference", "profile", "assessments", "recordings",
            "missions", "daily_reps", "spar_and_group_sessions", "events", "notifications", "devices", "milestones",
            "practice_log", "feedback_reports"} <= set(data)
    assert data["account"]["user_id"] and data["account"]["timezone"] == "Asia/Kolkata"
    assert data["account"]["locale"] and data["account"]["onboarding"]["age_confirmed"] is True
    rep = data["daily_reps"][0]
    assert rep["attempts"][0]["feedback"] is not None
    assert [t["is_user"] for t in rep["attempts"][0]["transcript"]] == [False, True, False]
    assert data["events"][0]["time"] == "11:00"
    by_title = {n["title"]: n for n in data["notifications"]}
    assert by_title["Notifications are on"]["push"] == "sent"
    # The rep's feedback push waits (the person was in the app when it landed).
    assert by_title["Feedback on today's rep is ready"]["push"] == "pending"
    device = data["devices"][0]
    assert device["push_token_registered"] is True and TOKEN not in response.text
    assert list(_media_urls(data)) == []


def test_deleting_the_account_removes_v2_data(client, audio_dir):
    client.app.state.services.push = RecordingSender()
    headers = signup(client)
    user_id = client.get("/v1/me", headers=headers).json()["user_id"]
    client.post("/v1/devices", headers=headers, json={"apns_token": TOKEN, "authorization": "authorized",
                                                      "timezone": "UTC"})
    client.post("/v1/notifications/test", headers=headers)
    client.get("/v1/daily/upcoming", headers=headers)
    _daily_attempt(client, headers, audio_dir)
    client.get("/v1/missions/business.m1.real", headers=headers)
    models = (Device, Notification, DailyAssignment, DailyAttempt, MissionOpen)
    with client.app.state.services.session_factory() as db:
        assert all(db.scalar(select(func.count()).select_from(m).where(m.user_id == user_id)) for m in models)
    assert client.delete("/v1/me", headers=headers).status_code == 204
    with client.app.state.services.session_factory() as db:
        for model in models:
            assert db.scalar(select(func.count()).select_from(model).where(model.user_id == user_id)) == 0, model


@pytest.mark.parametrize("market", ["us", "in"])
def test_demo_seed_v2(client, market):
    headers = signup(client, onboard=False, consent=False)
    response = client.post("/v1/dev/seed-demo", headers=headers, json={"pro": False, "market": market})
    assert response.status_code == 200, response.text
    seeded = response.json()
    assert {"daily_date", "previous_daily_date", "group_conversation_id", "panel_id"} <= set(seeded)

    me = client.get("/v1/me", headers=headers).json()
    assert me["market"] == market
    assert me["timezone"] == ("Asia/Kolkata" if market == "in" else "America/New_York")
    assert me["onboarding"]["age_confirmed"] is True and me["practice_settings"]["anchor"]

    today = client.get("/v1/daily", headers=headers).json()
    assert today["date"] == seeded["daily_date"] and today["completed"] is False and today["attempts"] == []
    previous = client.get(f"/v1/daily/{seeded['previous_daily_date']}", headers=headers).json()
    assert previous["completed"] is True and previous["prompt_id"] == "explain.job_to_kid"
    assert date.fromisoformat(seeded["previous_daily_date"]) == date.fromisoformat(seeded["daily_date"]) - timedelta(days=1)
    first, second = previous["attempts"]
    assert first["feedback"]["target_met"] == "partly" and first["feedback"]["where"]["quote"]
    assert first["feedback"]["one_change"].startswith("Try:")
    assert second["feedback"]["comparison"]["previous_attempt_id"] == first["id"]

    practice = client.get("/v1/progress", headers=headers).json()["practice"]
    assert practice["weeks_on_target"] >= 3 and practice["reps"] >= 8
    assert practice["this_week"]["met"] is True and practice["this_week"]["days"]

    inbox = client.get("/v1/notifications", headers=headers).json()
    assert len(inbox["items"]) == 4 and inbox["unread_count"] == 2
    assert {n["category"] for n in inbox["items"]} == {"event_prep", "results", "weekly_reveal"}

    event = client.get("/v1/events", headers=headers).json()["events"][0]
    assert event["id"] == seeded["event_id"] and event["time"]
    assert event["date"] == (date.fromisoformat(seeded["daily_date"]) + timedelta(days=1)).isoformat()
    assert event["kind"] == ("placement" if market == "in" else "interview")

    group = client.get(f"/v1/conversations/{seeded['group_conversation_id']}", headers=headers).json()
    assert group["kind"] == "group" and group["participants"][0]["id"] == "mod"
    assert any(t["speaker_id"] and t["speaker"] == "partner" for t in group["turns"][1:])
    report = client.get(f"/v1/spar/reports/{seeded['group_conversation_id']}", headers=headers).json()
    assert report["status"] == "complete" and report["outcome"]["label"]
    assert seeded["panel_id"] in market_content.PANELS_BY_ID
    if market == "in":
        assert seeded["panel_id"] == "gd.remote_work_india"

    spar = client.get(f"/v1/conversations/{seeded['spar_conversation_id']}", headers=headers).json()
    if market == "in":
        assert spar["partner"]["name"] == "Kevin"
    recording = client.get(f"/v1/recordings/{seeded['recording_complete_id']}", headers=headers).json()
    label = recording["result"]["context_label"]
    pattern = r"· \d{1,2} [A-Z][a-z]{2}$" if market == "in" else r"· [A-Z][a-z]{2} \d{1,2}$"
    assert re.search(pattern, label), label
    assert client.get("/v1/review/weekly", headers=headers).status_code == 200

    again = client.post("/v1/dev/seed-demo", headers=headers, json={"pro": False, "market": market}).json()
    assert again == seeded
    with client.app.state.services.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Notification)
                         .where(Notification.push_state == "pending")) == 0  # seeded items are never pushed
