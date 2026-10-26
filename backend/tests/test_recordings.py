from __future__ import annotations

import json

from app.domain.consents import RECORDING_VERSION
from tests.helpers import conversation_file, dims, enroll_voice, signup, speech_file, upload_recording

TURNS = [("low", 8.0), ("high", 7.0), ("low", 8.0), ("high", 7.0), ("low", 8.0), ("high", 6.0)]


def _confirm(client, headers, recording_id, decision, label=None):
    body = {"decision": decision}
    if label is not None:
        body["speaker_label"] = label
    return client.post(f"/v1/recordings/{recording_id}/speaker-confirmation", json=body, headers=headers)


def test_unreadable_file_fails_without_a_skill_result(client, audio_dir):
    headers = signup(client)
    path = audio_dir / "broken.m4a"
    path.write_bytes(b"\x00\x01garbage" * 500)
    body = upload_recording(client, headers, str(path)).json()
    assert body["status"] == "failed"
    assert body["recovery"]["problem"] == "file_unreadable"
    assert body["result"] is None


def test_too_quiet_recording_needs_recovery_audio_unclear(client, audio_dir):
    headers = signup(client)
    path = conversation_file(audio_dir, "quiet.m4a", TURNS, level_db=-60)
    body = upload_recording(client, headers, path).json()
    assert body["status"] == "needs_recovery"
    assert body["recovery"]["problem"] == "audio_unclear"
    assert body["quality"]["usable"] == "no"
    assert body["result"] is None
    assert "not how you communicate" in body["recovery"]["message"]


def test_first_conversation_requires_speaker_confirmation_then_assesses(client, audio_dir):
    headers = signup(client)
    path = conversation_file(audio_dir, "meeting.m4a", TURNS)
    body = upload_recording(client, headers, path).json()
    assert body["status"] == "needs_speaker_confirmation"
    assert body["attribution"]["requires_confirmation"] is True
    assert body["attribution"]["reason"] == "first_conversation"
    labels = [s["label"] for s in body["speakers"]]
    assert len(labels) == 2
    for speaker in body["speakers"]:
        assert speaker["sample_url"].startswith("/v1/media/")
        assert speaker["display_name"].startswith("Speaker ")
        assert client.get(speaker["sample_url"]).status_code == 200
    # Upload without a voice reference: we never guess the user.
    assert not any(s["is_proposed_user"] for s in body["speakers"])

    confirmed = _confirm(client, headers, body["id"], "choose", labels[0]).json()
    assert confirmed["status"] in ("complete", "needs_recovery")
    final = client.get(f"/v1/recordings/{body['id']}", headers=headers).json()
    assert final["attribution"]["status"] == "confirmed"
    assert final["attribution"]["user_speaker_label"] == labels[0]
    assert final["result"] is not None
    assert final["result"]["context_label"].startswith("Team sync")
    assert final["debrief"] is not None
    shares = final["debrief"]["talk_share"]
    assert abs(sum(s["share"] for s in shares) - 1.0) < 0.02
    assert sum(1 for s in shares if s["is_user"]) == 1

    transcript = client.get(f"/v1/recordings/{body['id']}/transcript", headers=headers).json()
    assert any(seg["is_user"] for seg in transcript["segments"])
    assert any(not seg["is_user"] for seg in transcript["segments"])


def test_choose_another_speaker_triggers_reassessment(client, audio_dir):
    headers = signup(client)
    path = conversation_file(audio_dir, "meeting.m4a", TURNS)
    body = upload_recording(client, headers, path).json()
    labels = [s["label"] for s in body["speakers"]]
    _confirm(client, headers, body["id"], "choose", labels[0])
    first = client.get(f"/v1/recordings/{body['id']}/transcript", headers=headers).json()
    first_user_text = [s["text"] for s in first["segments"] if s["is_user"]]

    corrected = _confirm(client, headers, body["id"], "choose", labels[1]).json()
    assert corrected["attribution"]["user_speaker_label"] == labels[1]
    second = client.get(f"/v1/recordings/{body['id']}/transcript", headers=headers).json()
    second_user_text = [s["text"] for s in second["segments"] if s["is_user"]]
    assert first_user_text != second_user_text
    history = client.get("/v1/profile", headers=headers).json()["history"]
    assert all(h["source_id"] == body["id"] for h in history)  # old estimates replaced, not duplicated
    assert len(history) == len({h["dimension"] for h in history})


def test_not_in_recording_withholds_personal_assessment(client, audio_dir):
    headers = signup(client)
    path = conversation_file(audio_dir, "others.m4a", TURNS)
    body = upload_recording(client, headers, path).json()
    result = _confirm(client, headers, body["id"], "not_present").json()
    assert result["status"] == "no_user"
    assert result["result"] is None
    assert result["attribution"]["status"] == "not_present"
    profile = client.get("/v1/profile", headers=headers).json()
    assert profile["history"] == []
    assert all(d["level"] is None for d in profile["dimensions"])


def test_voice_reference_matching_still_confirms_first_conversation(client, audio_dir):
    headers = signup(client)
    enrolled = enroll_voice(client, headers, speech_file(audio_dir, "me.m4a", seconds=24, speaker="low", seed=3)).json()
    assert enrolled["status"] == "active", enrolled
    body = upload_recording(client, headers, conversation_file(audio_dir, "m1.m4a", TURNS, seed=11)).json()
    assert body["status"] == "needs_speaker_confirmation"
    assert body["attribution"]["requires_confirmation"] is True
    proposed = [s for s in body["speakers"] if s["is_proposed_user"]]
    assert len(proposed) == 1 and proposed[0]["match"] in ("reference", "acoustic")
    confirmed = _confirm(client, headers, body["id"], "confirm").json()
    assert confirmed["attribution"]["status"] == "confirmed"

    second = upload_recording(client, headers, conversation_file(audio_dir, "m2.m4a", TURNS, seed=21)).json()
    if second["status"] == "needs_speaker_confirmation":
        # Weak or conflicting matches are re-checked — but it's no longer the first conversation.
        assert second["attribution"]["reason"] != "first_conversation"
    else:
        assert second["attribution"]["status"] == "auto"
        assert second["status"] in ("complete", "needs_recovery")


def test_live_recording_proposes_loudest_speaker_without_reference(client, audio_dir):
    headers = signup(client)
    path = conversation_file(audio_dir, "live.m4a", TURNS)
    body = upload_recording(client, headers, path, source="live", title="Coffee chat").json()
    assert body["source"] == "live"
    assert body["status"] == "needs_speaker_confirmation"
    proposed = [s for s in body["speakers"] if s["is_proposed_user"]]
    assert len(proposed) == 1 and proposed[0]["match"] == "loudest"


def test_recording_requires_attestation_and_consent(client, audio_dir):
    headers = signup(client)
    path = conversation_file(audio_dir, "x.m4a", TURNS[:2])
    with open(path, "rb") as handle:
        consent = json.dumps({"attested": False, "consent_version": RECORDING_VERSION})
        response = client.post("/v1/recordings", files={"audio": ("x.m4a", handle, "audio/mp4")},
                               data={"source": "upload", "consent": consent}, headers=headers)
    assert response.status_code == 422
    no_consent = signup(client, consent=False)
    assert upload_recording(client, no_consent, path).status_code == 403


def test_delete_recording_removes_results(client, audio_dir):
    headers = signup(client)
    body = upload_recording(client, headers, conversation_file(audio_dir, "d.m4a", TURNS)).json()
    _confirm(client, headers, body["id"], "choose", body["speakers"][0]["label"])
    assert client.delete(f"/v1/recordings/{body['id']}", headers=headers).status_code == 204
    assert client.get(f"/v1/recordings/{body['id']}", headers=headers).status_code == 404
    assert client.get("/v1/profile", headers=headers).json()["history"] == []
    listing = client.get("/v1/recordings", headers=headers).json()
    assert listing["items"] == []


def test_recording_result_is_scoped_and_evidence_gated(client, audio_dir):
    headers = signup(client)
    body = upload_recording(client, headers, conversation_file(audio_dir, "s.m4a", TURNS)).json()
    _confirm(client, headers, body["id"], "choose", body["speakers"][0]["label"])
    final = client.get(f"/v1/recordings/{body['id']}", headers=headers).json()
    result = final["result"]
    for dim in dims(result).values():
        if dim["status"] in ("assessed", "provisional"):
            assert dim["evidence"]
            assert all(m["source_type"] == "recording" for m in dim["evidence"])
        else:
            assert dim["level"] is None
