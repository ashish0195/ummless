from __future__ import annotations

import uuid

import numpy as np

from app.domain.consents import VOICE_REFERENCE_VERSION
from tests.audio_fixtures import encode, synth_speech
from tests.helpers import enroll_voice, signup, speech_file


def test_device_auth_is_idempotent_and_tokens_are_checked(client):
    device = str(uuid.uuid4())
    first = client.post("/v1/auth/device", json={"device_id": device, "platform": "ios"}).json()
    second = client.post("/v1/auth/device", json={"device_id": device, "platform": "ios"}).json()
    assert first["is_new"] is True and second["is_new"] is False
    assert first["user_id"] == second["user_id"]
    bad = client.get("/v1/me", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    assert bad.json() == {"error": {"code": "unauthorized", "message": "Please sign in again."}}
    assert client.get("/v1/me").status_code == 401


def test_health_is_public(client):
    body = client.get("/v1/health").json()
    assert body["status"] == "ok" and body["demo_mode"] is True


def test_me_defaults_and_onboarding_flow(client):
    token = client.post("/v1/auth/device", json={"device_id": str(uuid.uuid4())}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/v1/me", headers=headers).json()
    assert me["next_step"] == "onboarding"
    assert me["onboarding"]["completed"] is False and me["onboarding"]["language"] == "en"
    assert me["practice_settings"] == {"weekly_target": 3, "reminder_time": None, "reminder_days": []}
    assert me["entitlement"]["tier"] == "free"
    assert me["voice_reference"]["status"] == "none"
    assert me["demo_mode"] is True

    patched = client.patch("/v1/me", headers=headers, json={
        "onboarding": {"completed": True, "contexts_ranked": ["interviews", "meetings"], "ease_targets": ["concise"],
                       "goal_track": "negotiation", "language": "es-MX", "region": "US-NY"},
        "practice_settings": {"weekly_target": 4, "reminder_time": "18:30", "reminder_days": [5, 1, 3]},
    }).json()
    assert patched["next_step"] == "choose_input"
    assert patched["onboarding"]["language"] == "es"
    assert patched["onboarding"]["analysis_consented_at"] is None
    assert patched["practice_settings"]["reminder_days"] == [1, 3, 5]

    consented = client.patch("/v1/me", headers=headers,
                             json={"onboarding": {"analysis_consent_version": "analysis-2026-10"}}).json()
    assert consented["onboarding"]["analysis_consent_version"] == "analysis-2026-10"
    assert consented["onboarding"]["analysis_consented_at"]

    started = client.patch("/v1/me", headers=headers, json={"onboarding": {"course_started": True}}).json()
    assert started["next_step"] == "home"

    cleared = client.patch("/v1/me", headers=headers, json={"practice_settings": {"reminder_time": None}}).json()
    assert cleared["practice_settings"]["reminder_time"] is None

    invalid = client.patch("/v1/me", headers=headers, json={"practice_settings": {"reminder_time": "25:99"}})
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "validation_error"


def test_meta_describes_the_product(client):
    headers = signup(client)
    meta = client.get("/v1/meta", headers=headers).json()
    assert [d["id"] for d in meta["dimensions"]] == ["clarity", "structure", "listening", "warmth", "persuasion",
                                                    "concision", "storytelling"]
    assert [a["id"] for a in meta["activities"]] == ["meet_someone_new", "explain_interest", "respond_to_someone",
                                                    "make_a_case", "tell_a_story"]
    assert meta["assessment_estimate_minutes"] == [10, 15]
    assert {t["id"] for t in meta["tracks"]} == {"negotiation", "business", "conversational", "storytelling",
                                                 "public_speaking"}
    assert meta["pricing"]["monthly_usd"] == 14.99
    assert meta["consents"]["voice_reference"]["version"] == VOICE_REFERENCE_VERSION
    assert any("OpenAI" in b for b in meta["consents"]["analysis"]["bullets"])
    assert len(meta["languages"]) >= 10


def test_recording_rules_are_just_in_time_and_strict(client):
    headers = signup(client)
    ca = client.get("/v1/meta/recording-rules", params={"region": "US-CA"}, headers=headers).json()
    assert ca["rule"] == "all_party" and "California" in ca["region_name"]
    assert "everyone" in ca["policy"].lower()
    assert "not legal advice" in ca["disclaimer"]
    ny = client.get("/v1/meta/recording-rules", params={"region": "US-NY"}, headers=headers).json()
    assert ny["rule"] == "one_party"
    assert client.get("/v1/meta/recording-rules", params={"region": "US-OR"}, headers=headers).json()["rule"] == "mixed"
    assert client.get("/v1/meta/recording-rules", params={"region": "DE"}, headers=headers).json()["rule"] == "all_party"
    other = client.get("/v1/meta/recording-rules", params={"region": "ZZ"}, headers=headers).json()
    assert other["region"] == "OTHER" and other["rule"] == "unknown"
    assert len(other["regions"]) > 60


def test_consent_gate_blocks_audio_until_accepted(client, audio_dir):
    headers = signup(client, consent=False)
    response = client.post("/v1/assessments", json={"purpose": "baseline"}, headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "consent_required"
    mission = client.post("/v1/conversations", json={"kind": "mission", "mission_id": "business.m1.learn"},
                          headers=headers)
    assert mission.status_code == 403
    spar = client.post("/v1/conversations", json={"kind": "spar", "persona_id": "first_date"}, headers=headers)
    assert spar.status_code == 403


def test_voice_reference_enrollment_and_deletion(client, audio_dir):
    headers = signup(client)
    good = enroll_voice(client, headers, speech_file(audio_dir, "me.m4a", seconds=24)).json()
    assert good["status"] == "active"
    assert good["reference"]["status"] == "active"
    assert good["reference"]["consent_version"] == VOICE_REFERENCE_VERSION
    assert client.get("/v1/voice-reference", headers=headers).json()["status"] == "active"
    assert client.get("/v1/me", headers=headers).json()["voice_reference"]["status"] == "active"

    short = enroll_voice(client, headers, speech_file(audio_dir, "short.m4a", seconds=4)).json()
    assert short["status"] == "rejected"
    assert short["issues"][0]["code"] in ("too_short", "noisy")
    # A rejected retry keeps the previous reference.
    assert client.get("/v1/voice-reference", headers=headers).json()["status"] == "active"

    assert client.delete("/v1/voice-reference", headers=headers).status_code == 204
    assert client.get("/v1/voice-reference", headers=headers).json()["status"] == "none"


def test_voice_reference_rejects_two_voices_and_wrong_consent(client, audio_dir):
    headers = signup(client)
    two = np.concatenate([synth_speech(7, 115, 1.0, seed=1), synth_speech(7, 220, 1.17, seed=2),
                          synth_speech(7, 115, 1.0, seed=3), synth_speech(7, 220, 1.17, seed=4)])
    path = encode(two, str(audio_dir / "two.m4a"))
    body = enroll_voice(client, headers, path).json()
    assert body["status"] == "rejected"
    assert body["issues"][0]["code"] == "multiple_speakers"

    with open(speech_file(audio_dir, "ok.m4a", seconds=20), "rb") as handle:
        wrong = client.post("/v1/voice-reference", files={"audio": ("ok.m4a", handle, "audio/mp4")},
                            data={"consent_version": "old-version", "consent_accepted": "true"}, headers=headers)
    assert wrong.status_code == 422
