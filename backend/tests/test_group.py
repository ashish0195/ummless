"""Group conversations: panels per market, several AI voices per turn, the moderator's close, the report, gating
and graceful fallbacks."""

from __future__ import annotations

from dataclasses import replace

from app.ai.llm_schemas import GroupLine, GroupReply
from app.domain import market_content
from app.errors import AIUnavailableError
from app.services import tts
from tests.helpers import post_turn, signup, speech_file

SEED_PANEL = "gd.remote_work_india"


def _svc(client):
    return client.app.state.services


def _start(client, headers, panel_id: str = SEED_PANEL, **extra):
    return client.post("/v1/conversations", headers=headers, json={"kind": "group", "panel_id": panel_id, **extra})


def _turn(client, headers, audio_dir, conversation_id: str, name: str) -> dict:
    response = post_turn(client, headers, conversation_id, speech_file(audio_dir, f"{name}.m4a", seconds=12))
    assert response.status_code == 200, response.text
    return response.json()


def test_panels_are_ordered_for_the_market(client):
    india = signup(client)
    client.patch("/v1/me", headers=india, json={"onboarding": {"region": "IN"}})
    panels = client.get("/v1/group/panels", headers=india).json()["panels"]
    ids = [p["id"] for p in panels]
    assert SEED_PANEL in ids and panels[0]["markets"] == ["in"]
    seed = next(p for p in panels if p["id"] == SEED_PANEL)
    assert seed["kind"] == "group_discussion" and seed["is_free"] is True and seed["topic"]
    assert seed["participants"][0]["id"] == "mod" and len(seed["participants"]) >= 3
    assert set(seed["participants"][0]) == {"id", "name", "role", "voice", "symbol", "color_hex"}

    us = signup(client)
    us_panels = client.get("/v1/group/panels", headers=us).json()["panels"]
    assert sorted(p["id"] for p in us_panels) == sorted(ids)  # everyone can try every panel
    relevant = [market_content.relevance(tuple(p["markets"]), "us") for p in us_panels]
    assert relevant == sorted(relevant)


def test_group_discussion_end_to_end(client, audio_dir, monkeypatch):
    spoken: list[tuple[str, str | None]] = []
    monkeypatch.setattr(tts, "speak", lambda svc, db, text, voice, instructions: spoken.append((voice, instructions)))
    headers = signup(client)
    created = _start(client, headers)
    assert created.status_code == 200, created.text
    conv = created.json()
    panel = market_content.PANELS_BY_ID[SEED_PANEL]
    assert conv["kind"] == "group" and conv["partner"]["name"] == panel.moderator.name
    assert [p["id"] for p in conv["participants"]] == ["mod", *[p.id for p in panel.participants]]
    assert conv["turns"][0]["speaker_id"] == "mod" and conv["turns"][0]["text"] == panel.opening
    assert [t["speaker_id"] for t in conv["turns"][1:]] == [pid for pid, _ in panel.pre_user_lines[:2]]
    assert conv["max_user_turns"] == panel.max_user_turns and conv["awaiting"] == "user"
    assert spoken[0] == (panel.moderator.voice, panel.moderator.tts_instructions)
    first_speaker = next(p for p in panel.participants if p.id == panel.pre_user_lines[0][0])
    assert spoken[1] == (first_speaker.voice, first_speaker.tts_instructions)

    known = {p["id"] for p in conv["participants"]}
    result = None
    for index in range(panel.max_user_turns):
        result = _turn(client, headers, audio_dir, conv["id"], f"gd{index}")
        partner_turns = result["partner_turns"]
        assert 1 <= len(partner_turns) <= 2
        assert all(t["speaker"] == "partner" and t["speaker_id"] in known for t in partner_turns)
        assert result["partner_turn"] == partner_turns[-1]
        if result["done"]:
            break
    assert result is not None and result["done"] is True
    assert result["partner_turn"]["speaker_id"] == "mod"  # the moderator closes
    assert result["conversation"]["awaiting"] == "none"

    finished = client.post(f"/v1/conversations/{conv['id']}/finish", headers=headers).json()
    assert finished["result_ref"] == {"type": "spar_report", "id": conv["id"]}
    report = client.get(f"/v1/spar/reports/{conv['id']}", headers=headers).json()
    assert report["status"] == "complete" and report["outcome"]["label"] and report["momentum"] == []
    assert report["title"] == panel.title
    sessions = client.get("/v1/spar/sessions", headers=headers).json()["items"]
    assert sessions[0]["conversation_id"] == conv["id"] and sessions[0]["persona_name"] == panel.moderator.name
    progress = client.get("/v1/progress", headers=headers).json()
    assert "first_group" in {m["id"] for m in progress["milestones"]}
    assert progress["recent"][0]["type"] == "group_session"


def test_leaving_before_speaking_has_no_report(client):
    headers = signup(client)
    conv = _start(client, headers).json()
    finished = client.post(f"/v1/conversations/{conv['id']}/finish", headers=headers).json()
    assert finished["result_ref"] is None and finished["conversation"]["status"] == "finished"
    assert client.get(f"/v1/spar/reports/{conv['id']}", headers=headers).status_code == 404
    assert client.get("/v1/spar/sessions", headers=headers).json()["items"] == []


def test_locked_panels_need_pro_and_bad_requests_fail_cleanly(client, monkeypatch):
    locked = replace(market_content.PANELS_BY_ID[SEED_PANEL], id="gd.locked_for_test", is_free=False)
    monkeypatch.setitem(market_content.PANELS_BY_ID, locked.id, locked)
    headers = signup(client)
    refused = _start(client, headers, locked.id)
    assert refused.status_code == 402 and refused.json()["error"]["code"] == "subscription_required"
    client.post("/v1/billing/dev-grant", headers=headers, json={"tier": "pro"})
    assert _start(client, headers, locked.id).status_code == 200
    assert _start(client, headers, "gd.no_such_panel").status_code == 404
    assert client.post("/v1/conversations", headers=headers, json={"kind": "group"}).status_code == 422
    assert _start(client, signup(client, consent=False)).status_code == 403


def test_model_outage_and_bad_lines_fall_back_to_the_script(client, audio_dir, monkeypatch):
    headers = signup(client)
    conv = _start(client, headers).json()
    ai = _svc(client).ai

    def outage(_req):
        raise AIUnavailableError("down")

    monkeypatch.setattr(ai, "group_reply", outage)
    result = _turn(client, headers, audio_dir, conv["id"], "outage")
    assert len(result["partner_turns"]) == 1 and result["partner_turns"][0]["speaker_id"] in {"p1", "p2", "p3"}
    assert result["done"] is False

    monkeypatch.setattr(ai, "group_reply", lambda _req: GroupReply(lines=[
        GroupLine(speaker_id="nobody", text="I'm not on this panel."),
        GroupLine(speaker_id="p2", text="  "),
    ], end_discussion=False))
    result = _turn(client, headers, audio_dir, conv["id"], "badlines")
    assert [t["speaker_id"] for t in result["partner_turns"]] != ["nobody"] and len(result["partner_turns"]) == 1

    monkeypatch.setattr(ai, "group_reply", lambda _req: GroupReply(lines=[
        GroupLine(speaker_id="p1", text="One more thing."), GroupLine(speaker_id="p1", text="Really."),
        GroupLine(speaker_id="p2", text="Agreed."), GroupLine(speaker_id="p3", text="Me too."),
    ], end_discussion=False))
    result = _turn(client, headers, audio_dir, conv["id"], "merged")
    assert [t["speaker_id"] for t in result["partner_turns"]] == ["p1", "p2"]  # same voice merged, at most two
    assert result["partner_turns"][0]["text"] == "One more thing. Really."

    # At the last turn the moderator must close; a participant's last word is replaced by the scripted close.
    monkeypatch.setattr(ai, "group_reply", lambda _req: GroupReply(lines=[
        GroupLine(speaker_id="p1", text="I still disagree.")], end_discussion=True))
    result = _turn(client, headers, audio_dir, conv["id"], "closing")
    assert result["done"] is True and result["partner_turns"][-1]["speaker_id"] == "mod"
