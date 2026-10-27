from __future__ import annotations

from app.config import Settings
from app.main import create_app
from tests.conftest import ContractClient
from tests.helpers import dims, post_turn, signup, speech_file


def test_seed_demo_builds_a_rich_idempotent_state(client):
    headers = signup(client, consent=False, onboard=False)
    seeded = client.post("/v1/dev/seed-demo", json={"pro": False}, headers=headers)
    assert seeded.status_code == 200, seeded.text
    ids = seeded.json()
    assert all(ids[key] for key in ("assessment_id", "recording_needs_confirmation_id", "recording_complete_id",
                                    "mission_id", "spar_conversation_id", "event_id"))
    assert client.post("/v1/dev/seed-demo", json={"pro": False}, headers=headers).json() == ids

    me = client.get("/v1/me", headers=headers).json()
    assert me["onboarding"]["completed"] is True and me["onboarding"]["analysis_consent_version"]
    assert me["has_results"] is True and me["next_step"] == "home"

    assessment = client.get(f"/v1/assessments/{ids['assessment_id']}", headers=headers).json()
    assert assessment["status"] == "complete" and assessment["result"]["status"] == "partial"
    by_dim = dims(assessment["result"])
    assert sum(1 for d in by_dim.values() if d["status"] in ("assessed", "provisional")) == 5
    for missing in ("listening", "storytelling"):
        assert by_dim[missing]["status"] == "not_enough_evidence"
        assert by_dim[missing]["missing_reason"] and by_dim[missing]["next_step"]
    assert assessment["result"]["first_win"] and assessment["result"]["style"]["status"] == "provisional"

    pending = client.get(f"/v1/recordings/{ids['recording_needs_confirmation_id']}", headers=headers).json()
    assert pending["status"] == "needs_speaker_confirmation"
    assert sum(1 for s in pending["speakers"] if s["is_proposed_user"]) == 1
    assert all(s["sample_text"] for s in pending["speakers"])
    complete = client.get(f"/v1/recordings/{ids['recording_complete_id']}", headers=headers).json()
    assert complete["status"] == "complete" and complete["debrief"]["decisions"]
    assert complete["debrief"]["best_moment"]["quote"]

    mission = client.get(f"/v1/missions/{ids['mission_id']}", headers=headers).json()
    assert len(mission["attempts"]) == 2
    assert mission["attempts"][1]["feedback"]["comparison"]["previous_attempt_id"] == mission["attempts"][0]["id"]
    assert mission["reflections"][0]["coach_reply"]

    report = client.get(f"/v1/spar/reports/{ids['spar_conversation_id']}", headers=headers).json()
    assert report["status"] == "complete" and report["outcome"]["label"] == "Budget approved"
    sessions = {s["conversation_id"] for s in client.get("/v1/spar/sessions", headers=headers).json()["items"]}
    assert len(sessions) == 3 and ids["group_conversation_id"] in sessions  # two spars and the group discussion
    events = client.get("/v1/events", headers=headers).json()["events"]
    assert events[0]["id"] == ids["event_id"] and len(events[0]["prep"]) == 3

    profile = client.get("/v1/profile", headers=headers).json()
    assert profile["basis"] == "partial"
    assert dims(profile)["listening"]["status"] == "assessed"  # filled in by the 1:1 recording
    assert dims(profile)["storytelling"]["status"] == "not_enough_evidence"
    progress = client.get("/v1/progress", headers=headers).json()
    assert progress["practice"]["total_sessions"] >= 5 and progress["practice"]["missions_completed"] == 1
    assert len(progress["milestones"]) >= 6
    review = client.get("/v1/review/weekly", headers=headers).json()
    assert review["practice"]["sessions"] >= 5 and review["before_after"] is not None
    course = client.get("/v1/course", headers=headers).json()
    assert course["basis"] == "profile"


def test_seeded_pending_recording_can_be_confirmed(client):
    headers = signup(client)
    ids = client.post("/v1/dev/seed-demo", json={"pro": True}, headers=headers).json()
    assert client.get("/v1/me", headers=headers).json()["entitlement"]["tier"] == "pro"
    confirmed = client.post(f"/v1/recordings/{ids['recording_needs_confirmation_id']}/speaker-confirmation",
                            json={"decision": "confirm"}, headers=headers).json()
    assert confirmed["attribution"]["status"] == "confirmed"
    final = client.get(f"/v1/recordings/{ids['recording_needs_confirmation_id']}", headers=headers).json()
    assert final["status"] in ("complete", "needs_recovery")
    assert final["result"] is not None


def test_seed_demo_is_hidden_when_dev_tools_are_disabled(tmp_path):
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path}/p.db", media_dir=str(tmp_path / "m"),
                        jobs_inline=True, ai_provider="mock", allow_dev_entitlements=False)
    with ContractClient(create_app(settings)) as client:
        headers = signup(client)
        response = client.post("/v1/dev/seed-demo", json={"pro": True}, headers=headers)
        assert response.status_code == 404
        assert client.post("/v1/billing/dev-grant", json={"tier": "pro"}, headers=headers).status_code == 403


def test_feedback_reports_are_stored_and_validated(client):
    headers = signup(client)
    ok = client.post("/v1/feedback-reports", headers=headers, json={
        "target_type": "dimension_result", "target_id": "asm_123", "dimension": "listening", "reason": "misheard",
        "note": "That quote was my colleague, not me."})
    assert ok.status_code == 201
    body = ok.json()
    assert body["id"].startswith("fbk_") and body["message"].startswith("Thanks")
    bad = client.post("/v1/feedback-reports", headers=headers, json={
        "target_type": "dimension_result", "target_id": "asm_123", "reason": "because"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    bad_dim = client.post("/v1/feedback-reports", headers=headers, json={
        "target_type": "recording", "target_id": "rec_1", "dimension": "charisma", "reason": "other"})
    assert bad_dim.status_code == 422
    assert client.delete("/v1/me", headers=headers).status_code == 204


def test_harder_challenge_on_mission_conversations(client, audio_dir):
    headers = signup(client)
    free_id = client.get("/v1/course", headers=headers).json()["free_mission_id"]
    conv = client.post("/v1/conversations", headers=headers,
                       json={"kind": "mission", "mission_id": free_id, "difficulty": "brutal"}).json()
    assert conv["setup"]["difficulty"] == "brutal"
    assert "push back hard" in " ".join(conv["setup"]["tips"])
    result = post_turn(client, headers, conv["id"], speech_file(audio_dir, "h.m4a", seconds=10)).json()
    assert result["partner_turn"]["text"].startswith("Honestly, I'm not convinced.")
    normal = client.post("/v1/conversations", headers=headers, json={"kind": "mission", "mission_id": free_id}).json()
    assert normal["setup"]["difficulty"] is None
