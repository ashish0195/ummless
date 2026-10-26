from __future__ import annotations

from tests.helpers import complete_assessment, dims, post_turn, run_activity, signup, speech_file


def test_full_baseline_produces_evidence_backed_profile(client, audio_dir):
    headers = signup(client)
    assessment = complete_assessment(client, headers, audio_dir)
    assert assessment["status"] == "complete"
    assert assessment["estimate_minutes"] == [10, 15]
    assert all(a["status"] == "done" for a in assessment["activities"])
    result = assessment["result"]
    assert result["status"] in ("complete", "partial")
    assert len(result["dimensions"]) == 7
    by_dim = dims(result)
    assessed = [d for d in by_dim.values() if d["status"] in ("assessed", "provisional")]
    assert len(assessed) >= 5
    for dim in assessed:
        assert 1 <= dim["level"] <= 5
        assert dim["level_label"]
        assert dim["confidence"] in ("low", "moderate", "high")
        assert dim["evidence"], "every assessed dimension must cite moments"
        for moment in dim["evidence"]:
            assert moment["quote"]
            assert moment["source_type"] == "conversation"
            assert moment["audio_url"] and moment["audio_url"].startswith("/v1/media/")
        assert dim["context_label"].startswith("AI roleplay")
    assert result["speech_patterns"]["user_speech_seconds"] > 60
    assert result["first_win"] is not None
    assert result["style"]["status"] in ("ready", "provisional", "not_ready")

    me = client.get("/v1/me", headers=headers).json()
    assert me["has_results"] is True and me["next_step"] == "home"


def test_partial_profile_marks_missing_dimensions_without_levels(client, audio_dir):
    headers = signup(client)
    assessment = complete_assessment(client, headers, audio_dir, activity_ids=["tell_a_story"])
    result = assessment["result"]
    assert result["status"] == "partial"
    by_dim = dims(result)
    assert by_dim["storytelling"]["status"] in ("assessed", "provisional")
    for missing in ("listening", "persuasion"):
        dim = by_dim[missing]
        assert dim["status"] == "not_enough_evidence"
        assert dim["level"] is None and dim["level_label"] is None and dim["confidence"] is None
        assert dim["evidence"] == []
        assert dim["missing_reason"]
        assert dim["next_step"]["type"] == "activity"
    assert by_dim["listening"]["next_step"]["activity_id"] == "respond_to_someone"
    assert "back-and-forth to assess listening" in result["summary"]
    assert "upload another conversation, or continue with your current results" in result["summary"]
    recovery = result["recovery"]
    assert recovery["problem"] == "too_little_evidence"
    assert any(a["type"] == "gap_fill" and a["activity_id"] == "respond_to_someone" for a in recovery["actions"])
    assert any(a["type"] == "continue" for a in recovery["actions"])


def test_gap_fill_merges_into_profile(client, audio_dir):
    headers = signup(client)
    complete_assessment(client, headers, audio_dir, activity_ids=["tell_a_story"])
    before = client.get("/v1/profile", headers=headers).json()
    assert dims(before)["listening"]["status"] == "not_enough_evidence"
    story_before = dims(before)["storytelling"]

    gap = complete_assessment(client, headers, audio_dir, activity_ids=["respond_to_someone"], purpose="gap_fill",
                              target_dimensions=["listening"])
    assert gap["purpose"] == "gap_fill"
    after = client.get("/v1/profile", headers=headers).json()
    assert dims(after)["listening"]["status"] in ("assessed", "provisional")
    assert dims(after)["storytelling"]["level"] == story_before["level"]  # untouched by the gap-fill sample
    assert after["basis"] in ("partial", "assessment")
    assert len(after["sources"]) == 2


def test_skipping_everything_gives_none_and_starter_course(client, audio_dir):
    headers = signup(client)
    created = client.post("/v1/assessments", json={"purpose": "baseline"}, headers=headers).json()
    for activity in created["activities"]:
        skipped = client.post(f"/v1/assessments/{created['id']}/activities/{activity['id']}/skip", headers=headers)
        assert skipped.status_code == 200
    final = client.post(f"/v1/assessments/{created['id']}/finalize", headers=headers)
    assert final.status_code == 200
    body = client.get(f"/v1/assessments/{created['id']}", headers=headers).json()
    assert body["status"] == "needs_recovery"
    assert body["result"]["status"] == "none"
    assert all(d["level"] is None for d in body["result"]["dimensions"])
    actions = {a["type"] for a in body["result"]["recovery"]["actions"]}
    assert "starter_course" in actions


def test_activity_follow_ups_respond_to_the_user(client, audio_dir):
    headers = signup(client)
    created = client.post("/v1/assessments", json={"purpose": "baseline", "activity_ids": ["respond_to_someone"]},
                          headers=headers).json()
    conv = client.post(f"/v1/assessments/{created['id']}/activities/respond_to_someone/start", headers=headers).json()
    assert conv["turns"][0]["speaker"] == "partner"
    assert conv["turns"][0]["text"].startswith("I joined a new team")
    assert conv["partner"]["name"] == "Maya"
    path = speech_file(audio_dir, "advice.m4a", seconds=10)
    response = post_turn(client, headers, conv["id"], path,
                         mock_text="You should just bring the idea up in the next meeting, honestly.")
    body = response.json()
    assert body["partner_turn"]["text"] == "I think I mostly wanted to talk it through first. It's just — I kept " \
                                           "thinking the idea was probably obvious and I'd look silly."
    assert body["done"] is False and body["conversation"]["awaiting"] == "user"


def test_turn_audio_problems_ask_for_a_retry_without_scoring(client, audio_dir):
    headers = signup(client)
    created = client.post("/v1/assessments", json={"purpose": "baseline", "activity_ids": ["meet_someone_new"]},
                          headers=headers).json()
    conv = client.post(f"/v1/assessments/{created['id']}/activities/meet_someone_new/start", headers=headers).json()

    garbage = audio_dir / "broken.m4a"
    garbage.write_bytes(b"this is not audio" * 100)
    bad = post_turn(client, headers, conv["id"], str(garbage)).json()
    assert bad["retry_suggested"] is True and bad["partner_turn"] is None
    assert bad["user_turn"]["excluded"] is True
    assert bad["user_turn"]["quality"]["issues"][0]["code"] == "file_unreadable"

    quiet = speech_file(audio_dir, "quiet.m4a", seconds=8, level_db=-60)
    quiet_body = post_turn(client, headers, conv["id"], quiet).json()
    assert quiet_body["retry_suggested"] is True
    assert quiet_body["user_turn"]["quality"]["usable"] == "no"
    assert quiet_body["user_turn"]["quality"]["issues"][0]["code"] in ("too_quiet", "no_speech")

    good = speech_file(audio_dir, "good.m4a", seconds=10)
    good_body = post_turn(client, headers, conv["id"], good).json()
    assert good_body["retry_suggested"] is False and good_body["partner_turn"] is not None
    assert good_body["conversation"]["user_turns"] == 1


def test_finish_activity_early_then_finalize_is_partial_not_penalized(client, audio_dir):
    headers = signup(client)
    created = client.post("/v1/assessments", json={"purpose": "baseline", "activity_ids": ["explain_interest",
                                                                                           "tell_a_story"]},
                          headers=headers).json()
    run_activity(client, headers, created["id"], "tell_a_story", audio_dir)
    conv = client.post(f"/v1/assessments/{created['id']}/activities/explain_interest/start", headers=headers).json()
    path = speech_file(audio_dir, "one.m4a", seconds=27)
    post_turn(client, headers, conv["id"], path)
    finished = client.post(f"/v1/conversations/{conv['id']}/finish", headers=headers)
    assert finished.json()["result_ref"] == {"type": "assessment", "id": created["id"]}
    client.post(f"/v1/assessments/{created['id']}/finalize", headers=headers)
    body = client.get(f"/v1/assessments/{created['id']}", headers=headers).json()
    assert body["status"] == "complete"
    assert body["result"]["status"] == "partial"
