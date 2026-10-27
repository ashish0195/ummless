from __future__ import annotations

import base64
import json

from tests.helpers import complete_assessment, post_turn, signup, speech_file


def _start_mission(client, headers, mission_id, quick=False):
    return client.post("/v1/conversations", json={"kind": "mission", "mission_id": mission_id, "quick": quick},
                       headers=headers)


def _attempt(client, headers, audio_dir, mission_id, texts, quick=False):
    conv = _start_mission(client, headers, mission_id, quick=quick)
    assert conv.status_code == 200, conv.text
    conv = conv.json()
    assert conv["kind"] == "mission" and conv["setup"]["target_behavior"]
    for index, text in enumerate(texts):
        result = post_turn(client, headers, conv["id"], speech_file(audio_dir, f"m{index}.m4a", seconds=10),
                           mock_text=text).json()
        if result["done"]:
            break
    assert result["done"] is True
    finished = client.post(f"/v1/conversations/{conv['id']}/finish", headers=headers).json()
    assert finished["result_ref"]["type"] == "mission_attempt"
    return finished["result_ref"]["id"]


def test_course_is_goal_based_until_there_is_evidence(client, audio_dir):
    headers = signup(client)
    course = client.get("/v1/course", headers=headers).json()
    assert course["basis"] == "goal" and course["basis_label"] == "Based on your goal"
    assert course["track"]["id"] == "business"
    assert len(course["modules"]) == 4 and all(len(m["missions"]) == 4 for m in course["modules"])
    assert course["gap_tasks"] == []
    free_id = course["free_mission_id"]
    statuses = {m["id"]: m["status"] for mod in course["modules"] for m in mod["missions"]}
    assert statuses[free_id] == "available"
    assert sum(1 for s in statuses.values() if s == "available") == 1
    assert course["today"]["mission"]["id"] == free_id
    assert course["today"]["quick"]["minutes"] == 2

    complete_assessment(client, headers, audio_dir, activity_ids=["tell_a_story"])
    tailored = client.get("/v1/course", headers=headers).json()
    assert tailored["basis"] == "profile" and tailored["basis_label"] == "Tailored to your profile"
    assert tailored["gap_tasks"], "partial profiles get targeted gap tasks"
    assert all(g["activity_id"] for g in tailored["gap_tasks"])


def test_free_mission_attempts_feedback_and_retry_comparison(client, audio_dir):
    headers = signup(client)
    course = client.get("/v1/course", headers=headers).json()
    free_id = course["free_mission_id"]
    mission = client.get(f"/v1/missions/{free_id}", headers=headers).json()
    assert mission["status"] == "available"
    assert mission["example"]["text"] and mission["example"]["explanation"]
    assert mission["target_behavior"].startswith("State your recommendation")

    _attempt(client, headers, audio_dir, free_id, [
        "So I think maybe we should probably, um, look at both options before deciding anything.",
        "Okay, fair. I guess the second one is fine because it's cheaper.",
    ])
    _attempt(client, headers, audio_dir, free_id, [
        "I'd go with the second vendor. It's cheaper, and they passed our security review. What concerns do you have?",
        "Fair point. They've done three migrations like ours, so I'd still choose them — can we trial it for two weeks?",
    ])
    detail = client.get(f"/v1/missions/{free_id}", headers=headers).json()
    assert [a["attempt_number"] for a in detail["attempts"]] == [1, 2]
    first, second = (a["feedback"] for a in detail["attempts"])
    assert first["assessable"] in ("yes", "partly")
    assert first["where"]["audio_url"].startswith("/v1/media/")
    assert first["comparison"] is None
    assert second["comparison"]["previous_attempt_id"] == detail["attempts"][0]["id"]
    assert "shorter answer isn't automatically" in second["comparison"]["note"]

    done = client.post(f"/v1/missions/{free_id}/complete", json={"takeaway": "Lead with the recommendation."},
                       headers=headers).json()
    assert done["status"] == "completed" and done["takeaway"] == "Lead with the recommendation."
    progress = client.get("/v1/progress", headers=headers).json()
    assert progress["practice"]["missions_completed"] == 1
    assert {m["id"] for m in progress["milestones"]} >= {"first_mission", "first_retry"}


def test_locked_missions_return_402_but_preview_content(client):
    headers = signup(client)
    course = client.get("/v1/course", headers=headers).json()
    locked = next(m for mod in course["modules"] for m in mod["missions"] if m["status"] == "locked")
    preview = client.get(f"/v1/missions/{locked['id']}", headers=headers).json()
    assert preview["status"] == "locked" and preview["locked_reason"] == "subscribe"
    assert preview["context"]
    response = _start_mission(client, headers, locked["id"])
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "subscription_required"

    assert client.post("/v1/billing/dev-grant", json={"tier": "pro"}, headers=headers).json()["tier"] == "pro"
    assert _start_mission(client, headers, locked["id"]).status_code == 200


def test_quick_mission_is_one_exchange(client, audio_dir):
    headers = signup(client)
    free_id = client.get("/v1/course", headers=headers).json()["free_mission_id"]
    conv = _start_mission(client, headers, free_id, quick=True).json()
    assert conv["setup"]["quick"] is True and conv["max_user_turns"] == 1
    result = post_turn(client, headers, conv["id"], speech_file(audio_dir, "q.m4a", seconds=10)).json()
    assert result["done"] is True


def test_real_life_mission_reflection_and_change_focus(client):
    headers = signup(client)
    client.post("/v1/billing/dev-grant", json={"tier": "pro"}, headers=headers)
    course = client.get("/v1/course", headers=headers).json()
    real = next(m for m in course["modules"][0]["missions"] if m["type"] == "real_life")
    detail = client.get(f"/v1/missions/{real['id']}", headers=headers).json()
    assert detail["real_life"]["prompt"] and detail["real_life"]["reflection_questions"]
    reflection = client.post(f"/v1/missions/{real['id']}/reflections", headers=headers,
                             json={"text": "I led with my recommendation in standup. It felt odd but people agreed.",
                                   "went": "well"}).json()
    assert reflection["coach_reply"] and reflection["went"] == "well"
    client.post(f"/v1/missions/{real['id']}/complete", json={}, headers=headers)
    milestones = {m["id"] for m in client.get("/v1/progress", headers=headers).json()["milestones"]}
    assert "first_real_life" in milestones

    target = course["modules"][2]["id"]
    focused = client.post("/v1/course/focus", json={"module_id": target}, headers=headers).json()
    assert focused["focus_module_id"] == target
    switched = client.post("/v1/course/track", json={"track": "storytelling"}, headers=headers).json()
    assert switched["track"]["id"] == "storytelling"
    assert switched["modules"][0]["id"].startswith("storytelling.")


def test_spar_with_persona_whispers_and_report(client, audio_dir):
    headers = signup(client)
    personas = client.get("/v1/spar/personas", headers=headers).json()["personas"]
    assert {"skeptical_cfo", "tech_interviewer", "first_date"} <= {p["id"] for p in personas}
    free_persona = next(p for p in personas if p["is_free"])
    conv = client.post("/v1/conversations", json={"kind": "spar", "persona_id": free_persona["id"]},
                       headers=headers).json()
    assert conv["kind"] == "spar" and conv["setup"]["difficulty"] == free_persona["default_difficulty"]
    whispered = False
    for index in range(conv["max_user_turns"]):
        body = post_turn(client, headers, conv["id"], speech_file(audio_dir, f"s{index}.m4a", seconds=8)).json()
        whispered = whispered or bool(body["partner_turn"] and body["partner_turn"]["coach_whisper"])
        if body["done"]:
            break
    assert whispered
    finished = client.post(f"/v1/conversations/{conv['id']}/finish", headers=headers).json()
    assert finished["result_ref"] == {"type": "spar_report", "id": conv["id"]}
    report = client.get(f"/v1/spar/reports/{conv['id']}", headers=headers).json()
    assert report["status"] == "complete"
    assert report["outcome"]["label"]
    assert report["momentum"] and all(0 <= p["value"] <= 1 for p in report["momentum"])
    sessions = client.get("/v1/spar/sessions", headers=headers).json()["items"]
    assert sessions[0]["conversation_id"] == conv["id"]

    second = client.post("/v1/conversations", json={"kind": "spar", "persona_id": free_persona["id"]}, headers=headers)
    assert second.status_code == 402, "free tier: one spar per week"
    pro_only = next(p for p in personas if not p["is_free"])
    client.post("/v1/billing/dev-grant", json={"tier": "pro"}, headers=headers)
    assert client.post("/v1/conversations", json={"kind": "spar", "persona_id": pro_only["id"], "difficulty": "kind"},
                       headers=headers).status_code == 200
    custom = client.post("/v1/conversations", json={"kind": "spar", "custom_scenario": "Asking my landlord to fix "
                                                    "the heating", "difficulty": "real"}, headers=headers).json()
    assert custom["setup"]["context"] and custom["partner"]["name"]


def test_talks_and_events(client):
    headers = signup(client)
    talks = client.get("/v1/talks", headers=headers).json()["talks"]
    assert len(talks) >= 6 and talks[0]["is_free"] is True
    assert any(t["id"] == "gettysburg" for t in talks)
    free = client.get(f"/v1/talks/{talks[0]['id']}", headers=headers).json()
    assert free["locked"] is False and len(free["lines"]) == free["lines_count"]
    assert any("[pause]" in line["text"] for line in free["lines"])
    assert all(line["audio_url"] is None for line in free["lines"])  # demo mode → on-device speech
    locked = client.get("/v1/talks/gettysburg", headers=headers).json()
    assert locked["locked"] is True and len(locked["lines"]) == 2
    assert client.get("/v1/talks/gettysburg/lines/5/audio", headers=headers).status_code == 402

    event = client.post("/v1/events", headers=headers, json={"title": "Interview at Acme", "kind": "interview",
                                                             "date": "2026-11-02", "notes": "Product manager role"})
    assert event.status_code == 200
    event = event.json()
    assert len(event["prep"]) == 3 and [p["difficulty"] for p in event["prep"]][0] == "kind"
    assert client.get("/v1/events", headers=headers).json()["events"][0]["id"] == event["id"]
    client.post("/v1/billing/dev-grant", json={"tier": "pro"}, headers=headers)
    rehearsal = client.post("/v1/conversations", headers=headers, json={
        "kind": "spar", "event_id": event["id"], "prep_id": event["prep"][0]["id"], "difficulty": "kind"})
    assert rehearsal.status_code == 200
    assert client.delete(f"/v1/events/{event['id']}", headers=headers).status_code == 204
    assert client.post("/v1/events", headers=headers, json={"title": "x", "kind": "other",
                                                            "date": "not-a-date"}).status_code == 422


def test_weekly_review_keeps_estimates_without_new_evidence(client, audio_dir):
    headers = signup(client)
    empty = client.get("/v1/review/weekly", headers=headers).json()
    assert empty["practice"]["sessions"] == 0
    assert empty["skill_updates"] == []
    assert "stay as they were" in empty["evidence_note"]
    complete_assessment(client, headers, audio_dir, activity_ids=["tell_a_story"])
    review = client.get("/v1/review/weekly", headers=headers).json()
    assert review["practice"]["sessions"] == 1 and review["practice"]["days"] == 1
    assert any(u["change"] == "new_estimate" for u in review["skill_updates"])
    assert review["highlights"] and review["message"]
    assert review["next_focus_options"]


def test_progress_and_billing(client, audio_dir):
    headers = signup(client)
    progress = client.get("/v1/progress", headers=headers).json()
    assert progress["practice"]["total_sessions"] == 0 and progress["practice"]["this_week"]["target"] == 3

    # Outside production, Xcode's local StoreKit transactions are accepted unverified (tests/test_app_store.py covers
    # verification).
    payload = {"productId": "comlogue.pro.monthly", "bundleId": "com.comlogue.app", "transactionId": "1",
               "originalTransactionId": "1", "expiresDate": 4102444800000, "environment": "Sandbox"}
    jws = "e30." + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=") + ".sig"
    ent = client.post("/v1/billing/app-store", json={"signed_transaction": jws}, headers=headers).json()
    assert ent["tier"] == "pro" and ent["source"] == "app_store" and ent["expires_at"] == "2100-01-01T00:00:00Z"
    assert client.get("/v1/me", headers=headers).json()["entitlement"]["tier"] == "pro"
    bad = dict(payload, productId="something.else")
    bad_jws = "e30." + base64.urlsafe_b64encode(json.dumps(bad).encode()).decode().rstrip("=") + ".sig"
    assert client.post("/v1/billing/app-store", json={"signed_transaction": bad_jws},
                       headers=headers).status_code == 422
    no_expiry = {k: v for k, v in payload.items() if k != "expiresDate"}
    no_expiry_jws = "e30." + base64.urlsafe_b64encode(json.dumps(no_expiry).encode()).decode().rstrip("=") + ".sig"
    assert client.post("/v1/billing/app-store", json={"signed_transaction": no_expiry_jws},
                       headers=headers).status_code == 422
