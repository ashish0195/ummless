"""Write real API responses (demo provider) to ../contract-fixtures/ for the Swift decoding tests.

Usage (from backend/):  python scripts/export_contract_fixtures.py
Every response is also checked against the contract rules used by the test suite.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("ENVIRONMENT", "test")

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.conftest import ContractClient  # noqa: E402
from tests.helpers import (  # noqa: E402
    complete_assessment,
    conversation_file,
    enroll_voice,
    post_turn,
    signup,
    speech_file,
    upload_recording,
)

OUT = BACKEND.parent / "contract-fixtures"
TURNS = [("low", 8.0), ("high", 7.0), ("low", 8.0), ("high", 7.0), ("low", 8.0), ("high", 6.0)]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="comlogue-fixtures-"))
    audio = work / "audio"
    audio.mkdir()
    settings = Settings(environment="test", database_url=f"sqlite:///{work}/fixtures.db",
                        media_dir=str(work / "media"), jobs_inline=True, ai_provider="mock",
                        secret_key="fixtures", allow_dev_entitlements=True, rate_limit_ai_per_hour=100_000,
                        rate_limit_uploads_per_hour=100_000)
    written: list[str] = []

    def save(name: str, response) -> dict:
        assert response.status_code < 300, f"{name}: {response.status_code} {response.text}"
        data = response.json()
        (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        written.append(name)
        return data

    with ContractClient(create_app(settings)) as client:
        auth = client.post("/v1/auth/device", json={"device_id": "fixture-device-0001", "platform": "ios",
                                                    "app_version": "1.0"})
        save("auth_device.json", auth)
        headers = {"Authorization": f"Bearer {auth.json()['token']}"}
        save("profile_empty.json", client.get("/v1/profile", headers=headers))
        client.patch("/v1/me", headers=headers, json={
            "onboarding": {"completed": True, "contexts_ranked": ["meetings", "interviews", "social", "networking"],
                           "ease_targets": ["concise", "persuading"], "goal_track": "business", "language": "en",
                           "region": "US-CA", "age_confirmed": True, "analysis_consent_version": "analysis-2026-10"},
            "practice_settings": {"weekly_target": 3, "reminder_time": "08:30", "reminder_days": [1, 2, 3, 4, 5],
                                  "anchor": "After my morning coffee"},
        })
        save("device.json", client.post("/v1/devices", headers=headers, json={
            "apns_token": "a1" * 32, "push_environment": "sandbox", "authorization": "authorized",
            "timezone": "America/Los_Angeles", "locale": "en-US", "app_version": "2.0"}))
        save("me.json", client.get("/v1/me", headers=headers))
        save("meta.json", client.get("/v1/meta", headers=headers))
        save("recording_rules.json", client.get("/v1/meta/recording-rules", params={"region": "US-CA"},
                                                headers=headers))
        save("voice_reference_result.json",
             enroll_voice(client, headers, speech_file(audio, "me.m4a", seconds=24, speaker="low", seed=3)))

        # In-progress assessment with one started activity.
        created = client.post("/v1/assessments", json={"purpose": "baseline"}, headers=headers).json()
        conv = client.post(f"/v1/assessments/{created['id']}/activities/meet_someone_new/start", headers=headers)
        save("conversation.json", conv)
        turn = post_turn(client, headers, conv.json()["id"], speech_file(audio, "t1.m4a", seconds=12))
        save("turn_result.json", turn)
        save("assessment_in_progress.json", client.get(f"/v1/assessments/{created['id']}", headers=headers))

        # Complete baseline (separate assessment so every activity is covered).
        done = complete_assessment(client, headers, audio)
        (OUT / "assessment_complete.json").write_text(json.dumps(done, indent=2, ensure_ascii=False) + "\n")
        written.append("assessment_complete.json")
        save("assessments_list.json", client.get("/v1/assessments", headers=headers))

        # Recordings.
        pending = upload_recording(client, headers, conversation_file(audio, "meeting.m4a", TURNS, seed=11))
        pending_body = save("recording_needs_confirmation.json", pending)
        client.post(f"/v1/recordings/{pending_body['id']}/speaker-confirmation", json={"decision": "confirm"},
                    headers=headers)
        save("recording_complete.json", client.get(f"/v1/recordings/{pending_body['id']}", headers=headers))
        save("transcript.json", client.get(f"/v1/recordings/{pending_body['id']}/transcript", headers=headers))
        save("recordings_list.json", client.get("/v1/recordings", headers=headers))

        # Course & missions (Pro so every mission is open).
        save("entitlement.json", client.post("/v1/billing/dev-grant", json={"tier": "pro"}, headers=headers))
        course = save("course.json", client.get("/v1/course", headers=headers))
        mission_id = course["modules"][0]["missions"][0]["id"]
        finish = None
        for attempt, texts in enumerate([
            ["So I think maybe we should, um, look at both options first.", "I guess the cheaper one is fine."],
            ["I'd go with the second vendor. It's cheaper and passed security. What concerns do you have?",
             "Fair. They've done three migrations like ours, so I'd still choose them. Two-week trial?"],
        ]):
            mconv = client.post("/v1/conversations", json={"kind": "mission", "mission_id": mission_id},
                                headers=headers).json()
            for index, text in enumerate(texts):
                post_turn(client, headers, mconv["id"], speech_file(audio, f"m{attempt}{index}.m4a", seconds=10),
                          mock_text=text)
            finish = client.post(f"/v1/conversations/{mconv['id']}/finish", headers=headers)
        save("finish_result.json", finish)
        save("reflection.json", client.post(f"/v1/missions/{mission_id}/reflections", headers=headers, json={
            "text": "I led with my recommendation in standup and people responded faster.", "went": "well"}))
        save("mission.json", client.get(f"/v1/missions/{mission_id}", headers=headers))

        # Spar.
        save("personas.json", client.get("/v1/spar/personas", headers=headers))
        sconv = client.post("/v1/conversations", json={"kind": "spar", "persona_id": "skeptical_cfo"},
                            headers=headers).json()
        for index in range(sconv["max_user_turns"]):
            result = post_turn(client, headers, sconv["id"], speech_file(audio, f"s{index}.m4a", seconds=8)).json()
            if result["done"]:
                break
        client.post(f"/v1/conversations/{sconv['id']}/finish", headers=headers)
        save("spar_report.json", client.get(f"/v1/spar/reports/{sconv['id']}", headers=headers))
        save("spar_sessions.json", client.get("/v1/spar/sessions", headers=headers))

        # Talks, events, progress, review.
        save("talks.json", client.get("/v1/talks", headers=headers))
        save("talk.json", client.get("/v1/talks/decision_meeting", headers=headers))
        save("event.json", client.post("/v1/events", headers=headers, json={
            "title": "Final-round interview", "kind": "interview", "date": "2026-11-02", "time": "10:30",
            "notes": "Product manager role"}))
        save("events.json", client.get("/v1/events", headers=headers))
        past = client.post("/v1/events", headers=headers, json={
            "title": "Panel interview at Northwind", "kind": "interview", "date": "2026-10-20"}).json()
        save("event_reflected.json", client.post(f"/v1/events/{past['id']}/reflection", headers=headers, json={
            "text": "I led with my main point and the panel followed up on it.", "went": "well"}))
        # Daily rep (one attempt with feedback), the upcoming window, group conversations and the inbox.
        save("daily_upcoming.json", client.get("/v1/daily/upcoming", params={"days": 7}, headers=headers))
        dconv = client.post("/v1/conversations", json={"kind": "daily"}, headers=headers).json()
        post_turn(client, headers, dconv["id"], speech_file(audio, "rep.m4a", seconds=14))
        client.post(f"/v1/conversations/{dconv['id']}/finish", headers=headers)
        save("daily_rep.json", client.get("/v1/daily", headers=headers))
        save("panels.json", client.get("/v1/group/panels", headers=headers))
        gconv = save("group_conversation.json", client.post("/v1/conversations", headers=headers, json={
            "kind": "group", "panel_id": "gd.remote_work_india"}))
        post_turn(client, headers, gconv["id"], speech_file(audio, "g0.m4a", seconds=10))
        save("turn_result_group.json",  # the second turn: two participants respond
             post_turn(client, headers, gconv["id"], speech_file(audio, "g1.m4a", seconds=10)))
        client.post("/v1/notifications/test", headers=headers)
        inbox = client.get("/v1/notifications", headers=headers).json()
        client.post("/v1/notifications/read", headers=headers, json={"ids": [inbox["items"][-1]["id"]]})
        save("notifications.json", client.get("/v1/notifications", headers=headers))
        save("progress.json", client.get("/v1/progress", headers=headers))
        save("weekly_review.json", client.get("/v1/review/weekly", headers=headers))
        save("feedback_report.json", client.post("/v1/feedback-reports", headers=headers, json={
            "target_type": "dimension_result", "target_id": done["id"], "dimension": "listening",
            "reason": "misheard", "note": "That was my colleague."}))

        # Error envelope.
        error = client.get("/v1/recordings/rec_doesnotexist", headers=headers)
        (OUT / "error.json").write_text(json.dumps(error.json(), indent=2) + "\n")
        written.append("error.json")

        # Partial profile (separate user) and the dev seed.
        partial_user = signup(client)
        complete_assessment(client, partial_user, audio, activity_ids=["tell_a_story"])
        save("profile_partial.json", client.get("/v1/profile", headers=partial_user))
        seeded_user = signup(client, consent=False, onboard=False)
        save("seed_demo.json", client.post("/v1/dev/seed-demo", json={"pro": False, "market": "us"},
                                           headers=seeded_user))

    print(f"Wrote {len(written)} fixtures to {OUT}")
    for name in sorted(written):
        print("  ", name)


if __name__ == "__main__":
    main()
