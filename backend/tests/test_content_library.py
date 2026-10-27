"""Validates the market-aware content library (app/domain/content).

These are content rules, not behaviour: shapes, lengths, valid ids, and distribution minimums that keep daily
practice varied for every market.
"""

from __future__ import annotations

import re
from collections import Counter

from app.domain.consents import ANALYSIS, RECORDING, VOICE_REFERENCE
from app.domain.content.consent_translations import CONSENT_TRANSLATIONS
from app.domain.content.course_variants import COURSE_VARIANTS
from app.domain.content.daily_prompts import DAILY_PROMPTS
from app.domain.content.event_kinds import EVENT_KINDS
from app.domain.content.interviews_track import INTERVIEWS_TRACK, TRACK
from app.domain.content.panels import PANELS
from app.domain.content.personas_extra import MARKET_PERSONAS
from app.domain.content.schema import CONTEXTS, DAILY_KINDS, MARKETS, PANEL_KINDS
from app.domain.content.talks_extra import EXTRA_TALKS
from app.domain.course import MISSIONS, MODULES, TRACKS
from app.domain.dimensions import DIMENSION_IDS
from app.domain.personas import PERSONAS
from app.domain.talks import PAUSE_MARK, TALKS

VOICES = {"alloy", "ash", "ballad", "cedar", "coral", "echo", "fable", "marin", "nova", "onyx", "sage", "shimmer",
          "verse"}
DIFFICULTIES = {"kind", "real", "brutal"}
EVENT_KIND_ENUM = {"interview", "meeting", "presentation", "social", "negotiation", "other", "placement",
                   "group_discussion", "client_call", "viva", "appraisal"}
VALID_TRACKS = set(TRACKS) | {TRACK["id"]}
QUOTE = re.compile(r"“[^”]*”")
MISSION_SUFFIXES = ("learn", "remix", "real", "reveal")


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[.!?]+(?:\s+|$)", text) if s.strip()]


def _market_set(markets: tuple[str, ...]) -> frozenset[str]:
    return frozenset(markets)


# ---------------------------------------------------------------------------------------------- daily prompts


def test_daily_prompt_ids_are_unique_dotted_slugs():
    ids = [p.id for p in DAILY_PROMPTS]
    assert len(ids) == len(set(ids)), [i for i, n in Counter(ids).items() if n > 1]
    for prompt_id in ids:
        assert re.fullmatch(r"[a-z]+(\.[a-z0-9_]+)+", prompt_id), prompt_id


def test_daily_prompts_follow_the_writing_rules():
    for p in DAILY_PROMPTS:
        assert p.title and len(p.title) <= 48, (p.id, len(p.title))
        assert not p.title.endswith("."), p.id
        assert p.prompt == p.prompt.strip() and "  " not in p.prompt, p.id
        unquoted = QUOTE.sub("", p.prompt)
        assert 1 <= len(_sentences(unquoted)) <= 3, (p.id, unquoted)
        for quoted in QUOTE.findall(p.prompt):
            assert 1 <= len(_sentences(quoted.strip("“”"))) <= 2, (p.id, quoted)
        assert p.kind in DAILY_KINDS, p.id
        assert p.dimension in DIMENSION_IDS, p.id
        assert p.context in CONTEXTS, p.id
        assert p.target_behavior and len(p.target_behavior) <= 120, p.id
        assert len(p.tips) == 2 and all(t.strip() for t in p.tips), p.id
        assert 30 <= p.suggested_seconds <= 90, p.id
        assert p.markets and set(p.markets) <= set(MARKETS), p.id
        assert set(p.tracks) <= VALID_TRACKS, (p.id, p.tracks)
        assert p.level in (1, 2, 3), p.id
        assert all(1 <= m <= 12 for m in p.months) and len(set(p.months)) == len(p.months), p.id
        if p.example is not None:
            assert 0 < len(p.example.split()) <= 60, (p.id, len(p.example.split()))


def test_listening_reps_respond_to_a_quoted_line():
    for p in DAILY_PROMPTS:
        if p.dimension == "listening":
            assert p.kind == "respond", p.id
        if p.kind == "respond":
            assert QUOTE.search(p.prompt), f"{p.id} must quote what the other person says"


def test_daily_prompts_cover_every_dimension_kind_level_and_context():
    dimensions = Counter(p.dimension for p in DAILY_PROMPTS)
    for dimension in DIMENSION_IDS:
        assert dimensions[dimension] >= 12, (dimension, dimensions[dimension])
    assert {p.kind for p in DAILY_PROMPTS} == set(DAILY_KINDS)
    assert {p.level for p in DAILY_PROMPTS} == {1, 2, 3}
    assert {p.context for p in DAILY_PROMPTS} == set(CONTEXTS)
    assert sum(1 for p in DAILY_PROMPTS if p.months) >= 10


def test_every_market_has_a_full_week_of_variety():
    universal = frozenset(MARKETS)
    by_market = Counter(_market_set(p.markets) for p in DAILY_PROMPTS)
    assert by_market[universal] >= 40
    assert by_market[frozenset({"in"})] >= 30
    assert by_market[frozenset({"us"})] >= 30
    for market in MARKETS:
        available = [p for p in DAILY_PROMPTS if market in p.markets]
        assert len(available) >= 40, (market, len(available))
        # At least a month without repeats, and every skill represented.
        assert {p.dimension for p in available} == set(DIMENSION_IDS), market


def test_seed_prompts_are_kept():
    by_id = {p.id: p for p in DAILY_PROMPTS}
    assert by_id["explain.job_to_kid"].dimension == "clarity"
    assert by_id["introduce.placement_hr"].markets == ("in",)
    assert by_id["persuade.weekend_plan"].suggested_seconds == 30


# ---------------------------------------------------------------------------------------------- panels


def test_panels_are_well_formed():
    ids = [panel.id for panel in PANELS]
    assert len(ids) == len(set(ids))
    for panel in PANELS:
        assert panel.kind in PANEL_KINDS, panel.id
        assert panel.title and panel.scenario and panel.description and panel.user_role and panel.opening, panel.id
        assert 2 <= len(panel.participants) <= 3, panel.id
        people = (panel.moderator, *panel.participants)
        person_ids = [person.id for person in people]
        assert len(person_ids) == len(set(person_ids)), panel.id
        voices = [person.voice for person in people]
        assert set(voices) <= VOICES, (panel.id, voices)
        assert len(voices) == len(set(voices)), f"{panel.id}: every speaker needs a distinct voice"
        for person in people:
            assert person.name and person.role and person.stance and person.tts_instructions, (panel.id, person.id)
            assert re.fullmatch(r"#[0-9A-F]{6}", person.color_hex), (panel.id, person.id)
        participant_ids = {person.id for person in panel.participants}
        assert len(panel.pre_user_lines) <= 2, panel.id
        for speaker, line in panel.pre_user_lines:
            assert speaker in participant_ids and line.strip(), (panel.id, speaker)
        assert 3 <= len(panel.evaluation_focus) <= 5, panel.id
        assert 3 <= panel.max_user_turns <= 6, panel.id
        assert panel.minutes > 0, panel.id
        assert panel.markets and set(panel.markets) <= set(MARKETS), panel.id
        assert panel.default_difficulty in DIFFICULTIES, panel.id
        assert re.fullmatch(r"#[0-9A-F]{6}", panel.color_hex), panel.id


def test_exactly_one_free_group_discussion_and_one_free_panel_interview():
    free = Counter(panel.kind for panel in PANELS if panel.is_free)
    assert free == {"group_discussion": 1, "panel_interview": 1}
    kinds = Counter(panel.kind for panel in PANELS)
    assert kinds["group_discussion"] >= 4 and kinds["panel_interview"] >= 4
    markets_with_panels = {market for panel in PANELS for market in panel.markets}
    assert {"us", "in"} <= markets_with_panels


def test_seed_panel_is_kept():
    seed = next(panel for panel in PANELS if panel.id == "gd.remote_work_india")
    assert seed.kind == "group_discussion" and seed.is_free and seed.markets == ("in",)


# ---------------------------------------------------------------------------------------------- personas


def test_market_personas_are_complete():
    ids = [persona.id for persona in MARKET_PERSONAS]
    assert len(ids) == len(set(ids))
    for persona in MARKET_PERSONAS:
        # Personas may already be merged into PERSONAS by the backend; ids must not clash with a different persona.
        assert persona.id not in PERSONAS or PERSONAS[persona.id] is persona, persona.id
        for field in ("name", "title", "scenario", "description", "opening", "character", "win_condition",
                      "tts_instructions", "symbol"):
            assert getattr(persona, field).strip(), (persona.id, field)
        assert persona.default_difficulty in DIFFICULTIES, persona.id
        assert persona.voice in VOICES, persona.id
        assert persona.markets and set(persona.markets) <= set(MARKETS), persona.id
        assert re.fullmatch(r"#[0-9A-F]{6}", persona.color_hex), persona.id
    free = [persona for persona in MARKET_PERSONAS if persona.is_free]
    assert 1 <= len(free) <= 2
    assert {"us", "in"} <= {market for persona in MARKET_PERSONAS for market in persona.markets}
    assert any(persona.id == "us_client_escalation" for persona in MARKET_PERSONAS)


# ---------------------------------------------------------------------------------------------- interviews track


def _check_partner(partner: dict, where: str) -> None:
    for key in ("name", "role", "opening", "follow_up", "fallback"):
        assert isinstance(partner.get(key), str) and partner[key].strip(), (where, key)
    if "voice" in partner:
        assert partner["voice"] in VOICES, where


def test_interviews_track_modules_have_every_part():
    assert TRACK["id"] == "interviews" and TRACK["title"] and TRACK["symbol"]
    assert len(INTERVIEWS_TRACK) == 4
    assert INTERVIEWS_TRACK[0]["title"] == "Tell me about yourself"
    for index, module in enumerate(INTERVIEWS_TRACK, start=1):
        where = f"interviews.m{index}"
        for key in ("title", "dimension", "target", "summary", "why", "example", "example_explanation"):
            assert isinstance(module.get(key), str) and module[key].strip(), (where, key)
        assert module["dimension"] in DIMENSION_IDS, where
        for part in ("learn", "remix"):
            assert module[part]["context"].strip(), (where, part)
            _check_partner(module[part]["partner"], f"{where}.{part}")
        real = module["real"]
        assert real["prompt"].strip() and real["alt_title"].strip(), where
        assert len(real["questions"]) >= 2, where
        _check_partner(real["partner"], f"{where}.real")
    assert len({module["dimension"] for module in INTERVIEWS_TRACK}) == 4


# ---------------------------------------------------------------------------------------------- course variants

MODULE_FIELDS = {"example", "example_explanation", "why", "summary"}
MISSION_FIELDS = {"title", "context", "real_life_prompt", "ai_alternative_title", "partner"}
PARTNER_FIELDS = {"name", "role", "voice", "symbol", "color", "character", "opening", "follow_up", "fallback",
                  "tts_instructions"}


def _valid_ids() -> tuple[set[str], set[str]]:
    modules = set(MODULES)
    missions = set(MISSIONS)
    for index in range(1, len(INTERVIEWS_TRACK) + 1):
        module_id = f"interviews.m{index}"
        modules.add(module_id)
        missions.update(f"{module_id}.{suffix}" for suffix in MISSION_SUFFIXES)
    return modules, missions


def test_course_variant_keys_and_fields_are_valid():
    assert set(COURSE_VARIANTS) <= set(MARKETS)
    modules, missions = _valid_ids()
    for market, variants in COURSE_VARIANTS.items():
        for key, override in variants.items():
            assert override, (market, key)
            if key in modules:
                assert set(override) <= MODULE_FIELDS, (market, key, set(override) - MODULE_FIELDS)
            else:
                assert key in missions, (market, key)
                assert set(override) <= MISSION_FIELDS, (market, key, set(override) - MISSION_FIELDS)
                partner = override.get("partner", {})
                assert set(partner) <= PARTNER_FIELDS, (market, key, set(partner) - PARTNER_FIELDS)
                if "name" in partner:
                    assert partner.get("character", "").strip(), f"{key}: a renamed partner needs a character"
                if "voice" in partner:
                    assert partner["voice"] in VOICES, key
            for value in override.values():
                texts = value.values() if isinstance(value, dict) else [value]
                for text in texts:
                    assert isinstance(text, str) and text.strip(), (market, key)


def test_india_variants_cover_every_interview_mission_and_avoid_dollars():
    india = COURSE_VARIANTS["in"]
    for index in range(1, len(INTERVIEWS_TRACK) + 1):
        for suffix in ("learn", "remix", "real"):
            assert f"interviews.m{index}.{suffix}" in india, f"interviews.m{index}.{suffix}"
    for key, override in india.items():
        assert "$" not in repr(override), f"{key}: use rupees or lakh in India variants"
    # Seed entries used by other tests.
    assert "Pune vendor" in india["business.m1"]["example"]
    assert india["interviews.m1.learn"]["partner"]["name"] == "Ritu"


# ---------------------------------------------------------------------------------------------- event kinds


def test_event_kinds_match_the_api_enum():
    ids = [kind.id for kind in EVENT_KINDS]
    assert len(ids) == len(set(ids))
    assert set(ids) == EVENT_KIND_ENUM
    for kind in EVENT_KINDS:
        assert kind.title.strip() and kind.symbol.strip() and kind.prep_hint.strip(), kind.id
        assert kind.markets and set(kind.markets) <= set(MARKETS), kind.id
    assert {kind.id for kind in EVENT_KINDS if kind.markets == ("in",)} >= {"placement", "group_discussion", "viva"}


# ---------------------------------------------------------------------------------------------- talks


def test_extra_talks_are_complete_and_do_not_clash():
    extra_ids = [talk.id for talk in EXTRA_TALKS]
    assert len(extra_ids) == len(set(extra_ids))
    # The backend may append EXTRA_TALKS to TALKS; only a *different* talk with the same id is a clash.
    core_ids = {talk.id for talk in TALKS if all(talk is not extra for extra in EXTRA_TALKS)}
    assert not core_ids & set(extra_ids)
    for talk in EXTRA_TALKS:
        assert talk.title and talk.speaker and talk.source_note and talk.technique, talk.id
        assert 6 <= len(talk.lines) <= 10 or talk.year is None, talk.id
        assert all(line.strip() for line in talk.lines), talk.id
        assert any(PAUSE_MARK in line for line in talk.lines), talk.id
        assert talk.breakdown and talk.tags, talk.id
        assert 80 <= talk.wpm <= 180 and 0 < talk.avg_pause_seconds <= 3, talk.id
        assert talk.tts_voice in VOICES and talk.tts_instructions, talk.id
    vivekananda = next(talk for talk in EXTRA_TALKS if talk.speaker == "Swami Vivekananda")
    assert vivekananda.year == 1893 and vivekananda.lines[0].startswith("Sisters and Brothers of America")


# ---------------------------------------------------------------------------------------------- consent translations


def test_hindi_consents_cover_every_consent_like_for_like():
    english = {"analysis": ANALYSIS, "voice_reference": VOICE_REFERENCE, "recording": RECORDING}
    hindi = CONSENT_TRANSLATIONS["hi"]
    assert set(hindi) == set(english)
    devanagari = re.compile(r"[ऀ-ॿ]")
    for kind, text in hindi.items():
        assert devanagari.search(text["title"]) and devanagari.search(text["body"]), kind
        assert len(text["bullets"]) == len(english[kind].bullets), kind
        assert all(devanagari.search(bullet) for bullet in text["bullets"]), kind
