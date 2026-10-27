"""Shared flows for tests and contract-fixture export."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.domain.consents import ANALYSIS_VERSION, RECORDING_VERSION, VOICE_REFERENCE_VERSION
from tests.audio_fixtures import encode, synth_conversation, synth_speech

SPEAKER_F0 = {"low": (115.0, 1.0), "high": (215.0, 1.17), "mid": (165.0, 1.08)}


def signup(client, *, consent: bool = True, onboard: bool = True) -> dict[str, str]:
    response = client.post("/v1/auth/device", json={"device_id": str(uuid.uuid4()), "platform": "ios",
                                                     "app_version": "1.0"})
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['token']}"}
    patch: dict[str, Any] = {}
    if onboard:
        patch["onboarding"] = {"completed": True, "contexts_ranked": ["meetings", "interviews", "social", "networking"],
                               "ease_targets": ["concise", "persuading"], "goal_track": "business", "language": "en",
                               "region": "US-CA"}
    if consent:
        patch.setdefault("onboarding", {}).update({"age_confirmed": True, "analysis_consent_version": ANALYSIS_VERSION})
    if patch:
        assert client.patch("/v1/me", json=patch, headers=headers).status_code == 200
    return headers


def speech_file(directory: Path, name: str, seconds: float = 12.0, speaker: str = "low", level_db: float = -24.0,
                seed: int = 0) -> str:
    f0, scale = SPEAKER_F0[speaker]
    samples = synth_speech(seconds, f0=f0, formant_scale=scale, level_db=level_db, seed=seed)
    return encode(samples, str(directory / name))


def conversation_file(directory: Path, name: str, turns: list[tuple[str, float]], seed: int = 0,
                      level_db: float = -24.0) -> str:
    return encode(synth_conversation(turns, seed=seed, level_db=level_db), str(directory / name))


def post_turn(client, headers, conversation_id: str, path: str, *, mock_text: str | None = None,
              elapsed: float = 30.0):
    metrics = {"mock_transcript": mock_text} if mock_text else {}
    with open(path, "rb") as handle:
        return client.post(
            f"/v1/conversations/{conversation_id}/turns",
            files={"audio": (Path(path).name, handle, "audio/mp4")},
            data={"elapsed_seconds": str(elapsed), "client_metrics": json.dumps(metrics)},
            headers=headers,
        )


# Turn durations that create real opportunities (extended answers, a story-length turn).
ACTIVITY_TURN_SECONDS = {
    "meet_someone_new": [12, 10, 10],
    "explain_interest": [27, 10, 8],
    "respond_to_someone": [12, 12, 10],
    "make_a_case": [14, 12],
    "tell_a_story": [32, 12],
}


def run_activity(client, headers, assessment_id: str, activity_id: str, directory: Path,
                 texts: list[str] | None = None) -> dict:
    conv = client.post(f"/v1/assessments/{assessment_id}/activities/{activity_id}/start", headers=headers)
    assert conv.status_code == 200, conv.text
    conversation = conv.json()
    durations = ACTIVITY_TURN_SECONDS[activity_id]
    result = None
    for index, seconds in enumerate(durations):
        path = speech_file(directory, f"{activity_id}_{index}.m4a", seconds=seconds, seed=index + 7)
        mock_text = texts[index] if texts and index < len(texts) else None
        response = post_turn(client, headers, conversation["id"], path, mock_text=mock_text)
        assert response.status_code == 200, response.text
        result = response.json()
        if result["done"]:
            break
    assert result is not None and result["done"], "activity should finish within its turn budget"
    return result


def complete_assessment(client, headers, directory: Path, activity_ids: list[str] | None = None,
                        purpose: str = "baseline", target_dimensions: list[str] | None = None) -> dict:
    body: dict[str, Any] = {"purpose": purpose}
    if activity_ids is not None:
        body["activity_ids"] = activity_ids
    if target_dimensions is not None:
        body["target_dimensions"] = target_dimensions
    created = client.post("/v1/assessments", json=body, headers=headers)
    assert created.status_code == 200, created.text
    assessment = created.json()
    for activity in assessment["activities"]:
        run_activity(client, headers, assessment["id"], activity["id"], directory)
    finalized = client.post(f"/v1/assessments/{assessment['id']}/finalize", headers=headers)
    assert finalized.status_code == 200, finalized.text
    final = client.get(f"/v1/assessments/{assessment['id']}", headers=headers)
    assert final.status_code == 200
    return final.json()


def upload_recording(client, headers, path: str, *, source: str = "upload", title: str = "Team sync"):
    consent = {"attested": True, "region": "US-CA", "rule": "all_party", "consent_version": RECORDING_VERSION}
    with open(path, "rb") as handle:
        return client.post("/v1/recordings", files={"audio": (Path(path).name, handle, "audio/mp4")},
                           data={"source": source, "title": title, "consent": json.dumps(consent)}, headers=headers)


def enroll_voice(client, headers, path: str):
    with open(path, "rb") as handle:
        return client.post("/v1/voice-reference", files={"audio": (Path(path).name, handle, "audio/mp4")},
                           data={"consent_version": VOICE_REFERENCE_VERSION, "consent_accepted": "true"},
                           headers=headers)


def dims(result: dict) -> dict[str, dict]:
    return {d["dimension"]: d for d in result["dimensions"]}
