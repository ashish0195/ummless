from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.helpers import signup


def _day(offset: int) -> str:
    # Two days either side of "today" in UTC is safely past or future in every timezone.
    return (datetime.now(UTC).date() + timedelta(days=offset)).isoformat()


def test_reflecting_on_an_event_counts_once_as_real_life_practice(client):
    headers = signup(client)
    event = client.post("/v1/events", headers=headers, json={"title": "Final round at Northwind", "kind": "interview",
                                                             "date": _day(-2), "time": "11:00"}).json()
    assert event["reflection"] is None
    before = client.get("/v1/progress", headers=headers).json()["practice"]["total_sessions"]

    reflected = client.post(f"/v1/events/{event['id']}/reflection", headers=headers,
                            json={"text": "Led with my main point; the panel nodded.", "went": "well"})
    assert reflected.status_code == 200, reflected.text
    reflection = reflected.json()["reflection"]
    assert reflection["id"].startswith("rfl_") and reflection["went"] == "well" and reflection["coach_reply"]

    progress = client.get("/v1/progress", headers=headers).json()
    assert progress["practice"]["total_sessions"] == before + 1
    assert any(m["id"] == "first_real_life" for m in progress["milestones"])

    # Changing your mind updates the same reflection and doesn't count twice.
    again = client.post(f"/v1/events/{event['id']}/reflection", headers=headers,
                        json={"text": "Thinking about it, mixed.", "went": "mixed"}).json()["reflection"]
    assert again["id"] == reflection["id"] and again["went"] == "mixed"
    assert client.get("/v1/progress", headers=headers).json()["practice"]["total_sessions"] == before + 1
    listed = client.get("/v1/events", headers=headers).json()["events"]
    assert next(e for e in listed if e["id"] == event["id"])["reflection"]["text"] == "Thinking about it, mixed."


def test_event_reflection_waits_for_the_day_and_validates(client):
    headers = signup(client)
    upcoming = client.post("/v1/events", headers=headers, json={"title": "Pitch to the board", "kind": "presentation",
                                                                "date": _day(5)}).json()
    early = client.post(f"/v1/events/{upcoming['id']}/reflection", headers=headers, json={"text": "Not yet"})
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "conflict"
    assert client.post("/v1/events/evt_missing/reflection", headers=headers, json={"text": "x"}).status_code == 404
    past = client.post("/v1/events", headers=headers, json={"title": "Viva", "kind": "other", "date": _day(-2)}).json()
    assert client.post(f"/v1/events/{past['id']}/reflection", headers=headers, json={"text": ""}).status_code == 422
    assert client.post(f"/v1/events/{past['id']}/reflection", headers=headers,
                       json={"text": "ok", "went": "great"}).status_code == 422
    other = signup(client)
    assert client.post(f"/v1/events/{past['id']}/reflection", headers=other, json={"text": "Mine?"}).status_code == 404
