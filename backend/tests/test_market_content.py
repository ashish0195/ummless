"""Market content in the product: course variants (validated loudly), personas, the interviews track, event kinds,
India's recording rules, extra talks, and the fairness and Hinglish rules in prompts and transcription."""

from __future__ import annotations

import re
from datetime import date, timedelta
from types import SimpleNamespace

from app.ai import prompts
from app.ai.openai_provider import OpenAIProvider
from app.ai.types import (
    AssessmentRequest,
    AttemptRequest,
    AudioHint,
    GroupMember,
    GroupReplyRequest,
    PartnerReplyRequest,
    SparRequest,
)
from app.config import Settings
from app.domain import market_content
from app.domain.content.course_variants import COURSE_VARIANTS
from app.domain.content.talks_extra import EXTRA_TALKS
from app.domain.course import MISSIONS, MODULES
from app.domain.dimensions import DIMENSIONS
from app.domain.evidence import compute_stats, evidence_caps
from app.models import Conversation
from tests.helpers import signup

INDIA = {"onboarding": {"region": "IN-KA"}}


def _india(client) -> dict:
    headers = signup(client)
    assert client.patch("/v1/me", headers=headers, json=INDIA).json()["market"] == "in"
    return headers


# ------------------------------------------------------------------ course variants


def test_every_course_variant_key_is_known():
    assert market_content.variant_problems() == []


def test_unknown_variant_keys_fail_loudly(monkeypatch):
    monkeypatch.setitem(COURSE_VARIANTS, "in", {
        **COURSE_VARIANTS.get("in", {}),
        "business.m1.learn": {"titel": "Typo"},
        "business.m1": {"title": "Modules can't be renamed"},
        "business.m9": {"example": "No such module"},
        "business.m1.remix": {"partner": {"name": "Asha", "colour": "#000000"}},
        "business.m1.real": {"context": ""},
    })
    problems = "\n".join(market_content.variant_problems())
    assert "'titel'" in problems and "business.m1: unknown key 'title'" in problems
    assert "business.m9: no module or mission" in problems and "'colour'" in problems
    assert "renames the partner without a matching 'character'" in problems
    assert "business.m1.real: 'context' must be a non-empty string" in problems


def test_india_variant_renames_the_partner_everywhere(client):
    headers = _india(client)
    base = MISSIONS["interviews.m1.learn"]
    variant = COURSE_VARIANTS["in"]["interviews.m1.learn"]
    mission = client.get("/v1/missions/interviews.m1.learn", headers=headers).json()
    assert mission["context"] == variant["context"]
    steps = " ".join(mission["steps"])
    assert variant["partner"]["name"] in steps
    assert not re.search(rf"\b{re.escape(base.partner.name)}\b", steps)

    client.post("/v1/billing/dev-grant", headers=headers, json={"tier": "pro"})
    conv = client.post("/v1/conversations", headers=headers,
                       json={"kind": "mission", "mission_id": "interviews.m1.learn"}).json()
    assert conv["partner"]["name"] == variant["partner"]["name"] and conv["partner"]["voice"] == "coral"
    assert conv["turns"][0]["text"] == variant["partner"]["opening"]
    with client.app.state.services.session_factory() as db:
        state = db.get(Conversation, conv["id"]).state
    assert state["tts_instructions"] == variant["partner"]["tts_instructions"] and state["market"] == "in"

    us = signup(client)
    us_mission = client.get("/v1/missions/interviews.m1.learn", headers=us).json()
    assert us_mission["context"] == base.context and base.partner.name in " ".join(us_mission["steps"])


def test_variant_titles_and_module_examples_show_in_course_and_mission(client, monkeypatch):
    monkeypatch.setitem(COURSE_VARIANTS, "in", {**COURSE_VARIANTS.get("in", {}),
                                                "business.m1.remix": {"title": "Remix: the sangeet speech"}})
    headers = _india(client)
    course = client.get("/v1/course", headers=headers).json()
    titles = {m["id"]: m["title"] for module in course["modules"] for m in module["missions"]}
    assert titles["business.m1.remix"] == "Remix: the sangeet speech"
    assert client.get("/v1/missions/business.m1.remix", headers=headers).json()["title"] == "Remix: the sangeet speech"
    example = client.get("/v1/missions/business.m1.learn", headers=headers).json()["example"]["text"]
    assert example == COURSE_VARIANTS["in"]["business.m1"]["example"].strip('"“”')
    us_titles = {m["id"]: m["title"] for module in client.get("/v1/course", headers=signup(client)).json()["modules"]
                 for m in module["missions"]}
    assert us_titles["business.m1.remix"] == MISSIONS["business.m1.remix"].title


def test_renamed_partners_leave_no_stale_names():
    for market, entries in COURSE_VARIANTS.items():
        for key, override in entries.items():
            mission = MISSIONS.get(key)
            if mission is None or mission.partner is None or "name" not in (override.get("partner") or {}):
                continue
            variant = market_content.mission_for_market(mission, market)
            old = re.compile(rf"\b{re.escape(mission.partner.name)}\b")
            texts = [*variant.steps, variant.title, variant.context, variant.real_life_prompt or "",
                     variant.ai_alternative_title or "", variant.partner.opening, variant.partner.follow_up,
                     variant.partner.follow_up_fallback, variant.partner.character]
            stale = [t for t in texts if old.search(t)]
            assert not stale, f"{market}:{key} still says {mission.partner.name!r}: {stale}"


# ------------------------------------------------------------------ personas, tracks, events, rules, talks


def test_personas_follow_the_market(client):
    india = client.get("/v1/spar/personas", headers=_india(client)).json()["personas"]
    assert india[0]["id"] == "us_client_escalation"
    us = client.get("/v1/spar/personas", headers=signup(client)).json()["personas"]
    assert "us_client_escalation" not in {p["id"] for p in us}
    assert {p["id"] for p in us} <= {p["id"] for p in india} | {p.id for p in market_content.ALL_PERSONAS.values()
                                                               if "us" in p.markets}


def test_market_persona_can_be_sparred_with(client):
    headers = _india(client)
    client.post("/v1/billing/dev-grant", headers=headers, json={"tier": "pro"})
    conv = client.post("/v1/conversations", headers=headers,
                       json={"kind": "spar", "persona_id": "us_client_escalation"})
    assert conv.status_code == 200, conv.text
    assert conv.json()["partner"]["name"] == market_content.persona("us_client_escalation").name


def test_interviews_track(client):
    headers = signup(client)
    course = client.post("/v1/course/track", headers=headers, json={"track": "interviews"}).json()
    assert course["track"]["id"] == "interviews"
    assert any(m["title"] == "Tell me about yourself" for m in course["modules"])
    assert all(MODULES[m["id"]].track_id == "interviews" for m in course["modules"])


def test_events_accept_market_kinds_and_a_time(client, monkeypatch):
    headers = _india(client)
    seen = []
    ai = client.app.state.services.ai
    original = ai.event_prep
    monkeypatch.setattr(ai, "event_prep", lambda req: seen.append(req) or original(req))
    day = (date.today() + timedelta(days=3)).isoformat()
    created = client.post("/v1/events", headers=headers, json={"title": "Placement HR round", "kind": "placement",
                                                               "date": day, "time": "10:30"})
    assert created.status_code == 200, created.text
    event = created.json()
    assert event["time"] == "10:30" and event["kind"] == "placement" and len(event["prep"]) == 3
    kind = market_content.event_kind("placement")
    assert seen[0].kind_hint == kind.prep_hint and seen[0].market == "in" and seen[0].time == "10:30"
    assert client.get("/v1/events", headers=headers).json()["events"][0]["time"] == "10:30"
    no_time = client.post("/v1/events", headers=headers, json={"title": "GD", "kind": "group_discussion", "date": day})
    assert no_time.json()["time"] is None
    for bad in ({"time": "25:00"}, {"kind": "hackathon"}):
        response = client.post("/v1/events", headers=headers, json={"title": "X", "date": day, **bad})
        assert response.status_code == 422, bad


def test_india_recording_rules_mention_the_data_protection_act(client):
    headers = signup(client)
    rules = client.get("/v1/meta/recording-rules?region=IN-MH", headers=headers).json()
    text = " ".join(str(v) for v in rules.values())
    assert "Digital Personal Data Protection Act, 2023" in text and rules["region"] == "IN"


def test_extra_talks_are_listed(client):
    listed = {t["id"] for t in client.get("/v1/talks", headers=signup(client)).json()["talks"]}
    assert {t.id for t in EXTRA_TALKS} <= listed


# ------------------------------------------------------------------ fairness, Hinglish


def test_prompts_carry_the_fairness_rules():
    stats = compute_stats([])
    caps = evidence_caps(stats)
    assert set(caps) == set(DIMENSIONS)
    assessment, _ = prompts.assessment(AssessmentRequest(language="en", context_description="c", units=[],
                                                         stats=stats, caps=caps, style_eligible=False))
    attempt, _ = prompts.attempt_feedback(AttemptRequest(language="en", mission_title="m", target_behavior="t",
                                                         context="c", partner_name="p", units=[]))
    spar, _ = prompts.spar_report(SparRequest(language="en", persona_name="p", persona_title="t", scenario="s",
                                              difficulty="real", win_condition="w", units=[], momentum=[]))
    group_report, _ = prompts.spar_report(SparRequest(
        language="en", persona_name="A, B", persona_title="Group discussion", scenario="GD", difficulty="real",
        win_condition="", units=[], momentum=[], kind="group", evaluation_focus=["Bringing in quieter participants"]))
    for text in (assessment, attempt, spar, group_report):
        assert "Indian English" in text and "code-switching" in text and "global" in text.lower()
    assert "Bringing in quieter participants" in prompts._group_report(SparRequest(
        language="en", persona_name="A", persona_title="GD", scenario="GD", difficulty="real", win_condition="",
        units=[], momentum=[], kind="group", evaluation_focus=["Bringing in quieter participants"]))[1]


def test_hinglish_conversations_and_group_replies():
    request = PartnerReplyRequest(kind="spar", language="hinglish", partner_name="Kevin", partner_role="Client",
                                  partner_character="c", situation="s", step_key="respond", step_instruction="i",
                                  fallback_line="f", is_closing=False, history=[("USER", "Theek hai, let's start.")])
    instructions, _ = prompts.partner_reply(request)
    assert "Hinglish" in instructions and "Latin script" in instructions
    group_request = GroupReplyRequest(
        language="hinglish", panel_kind="group_discussion", title="GD", topic="Remote work", situation="s",
        user_role="Participant", members=[GroupMember(id="mod", name="Meera", role="Moderator", stance="m",
                                                      is_moderator=True),
                                          GroupMember(id="p1", name="Rohan", role="Participant", stance="r")],
        history=[("USER", "Main start karta hoon.")], is_closing=True, turns_left=0, fallback_lines=[])
    group_instructions, history = prompts.group_reply(group_request)
    assert "id p1: Rohan" in group_instructions and "Hinglish" in group_instructions
    assert "moderator (mod)" in group_instructions and "end_discussion to true" in group_instructions
    assert history.endswith("USER: Main start karta hoon.")


def test_hinglish_transcription_sends_no_language_hint(tmp_path):
    provider = OpenAIProvider(Settings(environment="test", openai_api_key="sk-test", ai_provider="openai"))
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"fake")
    calls: list[dict] = []

    class Transcriptions:
        def create(self, **kwargs):
            calls.append({k: v for k, v in kwargs.items() if k != "file"})
            if kwargs.get("response_format") == "diarized_json":
                segment = SimpleNamespace(speaker="A", start=0.0, end=1.0, text="Haan")
                return SimpleNamespace(segments=[segment], duration=1.0)
            return SimpleNamespace(text="Haan, let's start.", logprobs=[])

    provider.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=Transcriptions()))
    provider.transcribe(str(audio), language="hinglish", prompt="Haan, so basically…", hint=AudioHint())
    provider.diarize(str(audio), language="hinglish", known_speakers=[], hint=AudioHint())
    provider.transcribe(str(audio), language="hi", prompt=None, hint=AudioHint())
    assert "language" not in calls[0] and calls[0]["prompt"] == "Haan, so basically…"
    assert "language" not in calls[1]
    assert calls[2]["language"] == "hi"
