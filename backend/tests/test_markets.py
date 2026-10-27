"""Markets and time zones: market derivation, local weeks (India's half-hour offset, US DST), labels, pricing,
Me/Meta v2 fields, the age gate, planned breaks and the additive startup migration."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text

from app.domain.consents import ANALYSIS_VERSION
from app.domain.markets import default_timezone, market_for, relevance
from app.migrations import add_missing_columns
from app.services.meta import money
from app.timeutil import day_bounds, local_date, local_datetime, short_date, week_bounds, week_start
from tests.helpers import signup


@pytest.mark.parametrize(("region", "market"), [
    ("IN", "in"), ("IN-MH", "in"), ("in-ka", "in"), ("US", "us"), ("US-CA", "us"), ("US-IN", "us"),  # Indiana
    ("GB", "global"), ("", "global"), (None, "global"),
])
def test_market_for_region(region, market):
    assert market_for(region) == market


def test_market_defaults_and_relevance():
    assert default_timezone("in") == "Asia/Kolkata"
    assert default_timezone("us") == "America/New_York"
    assert default_timezone("global") == "UTC"
    assert relevance(("in",), "in") == 0 < relevance(("us", "in"), "in") == 1 < relevance(("us",), "in") == 2


def test_kolkata_half_hour_offset_week_boundary():
    tz = "Asia/Kolkata"
    # Monday 00:10 in Bengaluru is still Sunday 18:40 UTC: it belongs to Monday's local week.
    moment = datetime(2026, 10, 25, 18, 40, tzinfo=UTC)
    assert local_date(moment, tz) == date(2026, 10, 26)
    assert week_start(moment, tz) == date(2026, 10, 26)
    assert week_start(moment) == date(2026, 10, 19)  # in UTC it's the previous week
    start, end = week_bounds(moment, tz)
    assert start == datetime(2026, 10, 25, 18, 30, tzinfo=UTC) and end - start == timedelta(days=7)
    day_start, day_end = day_bounds(date(2026, 10, 27), tz)
    assert day_start == datetime(2026, 10, 26, 18, 30, tzinfo=UTC) and day_end - day_start == timedelta(hours=24)


def test_us_dst_boundary_keeps_wall_clock_times():
    tz = "America/New_York"
    # 2026-11-01 is the end of daylight saving time: that local day lasts 25 hours.
    start, end = day_bounds(date(2026, 11, 1), tz)
    assert end - start == timedelta(hours=25)
    before = local_datetime(date(2026, 10, 31), time(19, 0), tz)
    after = local_datetime(date(2026, 11, 2), time(19, 0), tz)
    assert before == datetime(2026, 10, 31, 23, 0, tzinfo=UTC)  # EDT, UTC−4
    assert after == datetime(2026, 11, 3, 0, 0, tzinfo=UTC)  # EST, UTC−5
    # The week containing the change still runs Monday 00:00 to Monday 00:00 local.
    week_start_utc, week_end_utc = week_bounds(datetime(2026, 11, 1, 12, 0, tzinfo=UTC), tz)
    assert week_start_utc == datetime(2026, 10, 26, 4, 0, tzinfo=UTC)
    assert week_end_utc == datetime(2026, 11, 2, 5, 0, tzinfo=UTC)


def test_short_date_labels_follow_the_market_and_local_calendar():
    moment = datetime(2026, 10, 26, 20, 0, tzinfo=UTC)  # already 27 Oct in India
    assert short_date(moment, "in", "Asia/Kolkata") == "27 Oct"
    assert short_date(moment, "us", "America/New_York") == "Oct 26"
    assert short_date(moment) == "Oct 26"


def test_money_formats_rupees_with_indian_grouping():
    assert money(399, "INR") == "₹399"
    assert money(2499, "INR") == "₹2,499"
    assert money(124999.5, "INR") == "₹1,24,999.50"
    assert money(14.99, "USD") == "$14.99"
    assert money(1234.5, "USD") == "$1,234.50"


def _region(client, headers, region: str) -> dict:
    response = client.patch("/v1/me", headers=headers, json={"onboarding": {"region": region}})
    assert response.status_code == 200, response.text
    return response.json()


def test_meta_v2_pricing_by_market_event_kinds_support_and_translations(client):
    headers = signup(client)
    meta = client.get("/v1/meta", headers=headers).json()
    assert meta["pricing"]["currency"] == "USD" and meta["pricing"]["monthly_display"] == "$14.99"
    assert set(meta["pricing_by_market"]) == {"us", "in", "global"}
    india = meta["pricing_by_market"]["in"]
    assert (india["currency"], india["monthly_price"], india["yearly_price"]) == ("INR", 399, 2499)
    assert (india["monthly_display"], india["yearly_display"]) == ("₹399", "₹2,499")
    assert india["trial_days"] == 7 and india["monthly_usd"] == 14.99  # USD reference values stay
    assert meta["pricing_by_market"]["global"]["yearly_display"] == "$95.99"
    kinds = {k["id"]: k for k in meta["event_kinds"]}
    assert {"interview", "placement", "group_discussion", "meeting", "other"} <= set(kinds)
    assert kinds["placement"]["markets"] == ["in"]
    assert meta["support"]["email"] and meta["support"]["grievance_email"]
    assert "grievance_officer" in meta["support"]
    assert {"code": "hinglish", "name": "Hinglish (Hindi + English)"} in meta["languages"]
    for consent in meta["consents"].values():
        assert isinstance(consent["translations"], dict)

    _region(client, headers, "IN-KA")
    meta_in = client.get("/v1/meta", headers=headers).json()
    assert meta_in["pricing"]["currency"] == "INR" and meta_in["pricing"]["monthly_display"] == "₹399"


def test_me_v2_market_timezone_and_notification_settings(client):
    headers = signup(client)
    me = client.get("/v1/me", headers=headers).json()
    assert me["market"] == "us" and me["timezone"] == "America/New_York"
    assert me["notification_settings"] == {
        "practice_reminders": True, "event_prep": True, "results": True, "check_ins": True, "nudges": True,
        "weekly_reveal": True, "tips": False, "quiet_start": "22:00", "quiet_end": "08:00",
    }
    me = _region(client, headers, "IN")
    assert me["market"] == "in" and me["timezone"] == "Asia/Kolkata"
    me = _region(client, headers, "GB")
    assert me["market"] == "global" and me["timezone"] == "UTC"

    patched = client.patch("/v1/me", headers=headers, json={"notification_settings": {
        "nudges": False, "quiet_start": "23:30", "quiet_end": "07:00"}}).json()
    settings = patched["notification_settings"]
    assert settings["nudges"] is False and settings["quiet_start"] == "23:30" and settings["results"] is True
    bad = client.patch("/v1/me", headers=headers, json={"notification_settings": {"quiet_start": "7pm"}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"


def test_analysis_consent_requires_age_confirmation(client):
    token = client.post("/v1/auth/device", json={"device_id": str(uuid.uuid4())}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    refused = client.patch("/v1/me", headers=headers, json={"onboarding": {"analysis_consent_version": ANALYSIS_VERSION}})
    assert refused.status_code == 422
    assert client.get("/v1/me", headers=headers).json()["onboarding"]["analysis_consent_version"] is None
    assert client.patch("/v1/me", headers=headers, json={"onboarding": {"age_confirmed": True}}).status_code == 200
    accepted = client.patch("/v1/me", headers=headers,
                            json={"onboarding": {"analysis_consent_version": ANALYSIS_VERSION}}).json()
    assert accepted["onboarding"]["age_confirmed"] is True
    assert accepted["onboarding"]["analysis_consent_version"] == ANALYSIS_VERSION


def test_practice_anchor_and_planned_break(client):
    headers = signup(client)
    today = date.fromisoformat(client.get("/v1/daily", headers=headers).json()["date"])
    until = (today + timedelta(days=6)).isoformat()
    me = client.patch("/v1/me", headers=headers, json={"practice_settings": {
        "anchor": "  After my morning chai  ", "paused_until": until}}).json()
    assert me["practice_settings"]["anchor"] == "After my morning chai"
    assert me["practice_settings"]["paused_until"] == until
    assert client.get("/v1/progress", headers=headers).json()["practice"]["paused_until"] == until
    ended = client.patch("/v1/me", headers=headers, json={"practice_settings": {"paused_until": None,
                                                                                  "anchor": ""}}).json()
    assert ended["practice_settings"]["paused_until"] is None and ended["practice_settings"]["anchor"] is None
    bad = client.patch("/v1/me", headers=headers, json={"practice_settings": {"paused_until": "next week"}})
    assert bad.status_code == 422


def test_startup_migration_adds_new_nullable_columns(tmp_path):
    url = f"sqlite:///{tmp_path}/old.db"
    engine = create_engine(url)
    with engine.begin() as connection:  # a v1 table without the v2 columns
        connection.execute(text("CREATE TABLE users (id VARCHAR(40) PRIMARY KEY, device_id VARCHAR(160), "
                                "created_at DATETIME)"))
        connection.execute(text("INSERT INTO users (id, device_id) VALUES ('usr_old', 'dev-old')"))
        connection.execute(text("CREATE TABLE events (id VARCHAR(40) PRIMARY KEY, user_id VARCHAR(40), "
                                "title VARCHAR(200), kind VARCHAR(20), date VARCHAR(10))"))
    added = add_missing_columns(engine)
    assert {"users.timezone", "users.locale", "users.notification_settings", "events.time"} <= set(added)
    columns = {c["name"] for c in inspect(engine).get_columns("users")}
    assert {"timezone", "locale", "notification_settings"} <= columns
    with engine.begin() as connection:
        assert connection.execute(text("SELECT id, timezone FROM users")).one() == ("usr_old", None)
    assert add_missing_columns(engine) == []  # idempotent
