"""Market-aware views over the content: personas, course variants, event kinds, daily prompts and panels.

The data lives in `domain/content/`; this module only selects, orders and applies variants, so any amount of
content works.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .content.course_variants import COURSE_VARIANTS
from .content.daily_prompts import DAILY_PROMPTS
from .content.event_kinds import EVENT_KINDS
from .content.panels import PANELS
from .content.personas_extra import MARKET_PERSONAS
from .content.schema import DailyPromptDef, EventKindDef, PanelDef
from .course import MISSIONS, MODULES, MissionDef, ModuleDef, PartnerDef
from .markets import MARKETS, relevance
from .personas import PERSONAS, PersonaDef

# ------------------------------------------------------------------ personas

ALL_PERSONAS: dict[str, PersonaDef] = {**PERSONAS, **{p.id: p for p in MARKET_PERSONAS}}


def personas_for(market: str) -> list[PersonaDef]:
    """Personas offered in this market, made-for-this-market first (stable within each group)."""
    offered = [p for p in ALL_PERSONAS.values() if market in p.markets]
    return sorted(offered, key=lambda p: relevance(p.markets, market))


def persona(persona_id: str) -> PersonaDef | None:
    return ALL_PERSONAS.get(persona_id)


# ------------------------------------------------------------------ course variants

# Override key → dataclass field. Content may only use these keys (tests/test_market_content.py checks it).
MODULE_KEYS = {"example": "example_text", "example_explanation": "example_explanation", "why": "why_it_matters",
               "summary": "summary"}
MISSION_KEYS = {"title": "title", "context": "context", "real_life_prompt": "real_life_prompt",
                "ai_alternative_title": "ai_alternative_title"}
PARTNER_KEYS = {"name": "name", "role": "role", "voice": "voice", "symbol": "symbol", "color": "color_hex",
                "color_hex": "color_hex", "character": "character", "opening": "opening", "follow_up": "follow_up",
                "fallback": "follow_up_fallback", "follow_up_fallback": "follow_up_fallback",
                "tts_instructions": "tts_instructions"}


def _variant(market: str, key: str) -> dict[str, Any]:
    return COURSE_VARIANTS.get(market, {}).get(key) or {}


def module_for_market(module: ModuleDef, market: str) -> ModuleDef:
    override = _variant(market, module.id)
    changes = {field: override[key] for key, field in MODULE_KEYS.items() if key in override}
    return replace(module, **changes) if changes else module


def partner_for_market(partner: PartnerDef, overrides: dict[str, Any]) -> PartnerDef:
    changes = {field: overrides[key] for key, field in PARTNER_KEYS.items() if key in overrides}
    return replace(partner, **changes) if changes else partner


def _swap_name(text: str, old: str, new: str) -> str:
    return re.sub(rf"\b{re.escape(old)}\b", new, text)


def mission_for_market(mission: MissionDef, market: str) -> MissionDef:
    """The mission as offered in `market`: title, context, prompts and partner overridden by the content.

    The generated steps name the partner ("Jordan starts the conversation…"), so a renamed partner is swapped in.
    """
    override = _variant(market, mission.id)
    if not override:
        return mission
    changes: dict[str, Any] = {field: override[key] for key, field in MISSION_KEYS.items() if key in override}
    if mission.type == "real_life" and "real_life_prompt" in override and "context" not in override:
        changes["context"] = override["real_life_prompt"]  # a real-life mission's context is its prompt
    if mission.partner is not None and isinstance(override.get("partner"), dict):
        partner = partner_for_market(mission.partner, override["partner"])
        changes["partner"] = partner
        if partner.name != mission.partner.name:
            changes["steps"] = tuple(_swap_name(step, mission.partner.name, partner.name) for step in mission.steps)
    return replace(mission, **changes) if changes else mission


def mission_title(mission_id: str, market: str) -> str:
    return mission_for_market(MISSIONS[mission_id], market).title


def variant_problems() -> list[str]:
    """Everything wrong with COURSE_VARIANTS (unknown ids or keys, empty values). Empty when the content is valid."""
    problems: list[str] = []
    for market, entries in COURSE_VARIANTS.items():
        if market not in MARKETS:
            problems.append(f"{market}: unknown market")
        for key, override in entries.items():
            where = f"{market}:{key}"
            if key in MODULES:
                allowed = set(MODULE_KEYS)
            elif key in MISSIONS:
                allowed = set(MISSION_KEYS) | ({"partner"} if MISSIONS[key].partner is not None else set())
            else:
                problems.append(f"{where}: no module or mission with this id")
                continue
            for field, value in override.items():
                if field not in allowed:
                    problems.append(f"{where}: unknown key {field!r} (allowed: {sorted(allowed)})")
                elif field != "partner" and not (isinstance(value, str) and value.strip()):
                    problems.append(f"{where}: {field!r} must be a non-empty string")
            partner = override.get("partner")
            if partner is None or "partner" not in allowed:
                continue
            if not isinstance(partner, dict):
                problems.append(f"{where}: 'partner' must be a dict")
                continue
            for field, value in partner.items():
                if field not in PARTNER_KEYS:
                    problems.append(f"{where}: unknown partner key {field!r} (allowed: {sorted(PARTNER_KEYS)})")
                elif not (isinstance(value, str) and value.strip()):
                    problems.append(f"{where}: partner {field!r} must be a non-empty string")
            if "name" in partner and "character" not in partner:
                problems.append(f"{where}: renames the partner without a matching 'character'")
    return problems


# ------------------------------------------------------------------ event kinds

_BASE_EVENT_KINDS: tuple[EventKindDef, ...] = (
    EventKindDef(id="interview", title="Job interview", symbol="person.crop.rectangle",
                 markets=("us", "in", "global"),
                 prep_hint="Tell me about yourself, one behavioural story, a tough question and a question to ask."),
    EventKindDef(id="meeting", title="Meeting", symbol="person.2", markets=("us", "in", "global"),
                 prep_hint="Your opening update, a pushback moment, and closing with a clear next step."),
    EventKindDef(id="presentation", title="Presentation", symbol="person.wave.2", markets=("us", "in", "global"),
                 prep_hint="Opening line, your key message in one sentence, and handling a tough audience question."),
    EventKindDef(id="negotiation", title="Negotiation", symbol="scalemass", markets=("us", "in", "global"),
                 prep_hint="Anchoring your ask, handling the first counter, and agreeing next steps."),
    EventKindDef(id="social", title="Social event", symbol="party.popper", markets=("us", "in", "global"),
                 prep_hint="Introducing yourself, keeping a conversation going, and exiting gracefully."),
    EventKindDef(id="other", title="Something else", symbol="calendar", markets=("us", "in", "global"),
                 prep_hint="The most likely conversation, a tricky moment, and the outcome you want."),
)


def event_kinds() -> list[EventKindDef]:
    """Content kinds first in their order, then any base kind the content doesn't define."""
    by_id: dict[str, EventKindDef] = {}
    for kind in EVENT_KINDS:
        by_id.setdefault(kind.id, kind)
    for kind in _BASE_EVENT_KINDS:
        by_id.setdefault(kind.id, kind)
    return list(by_id.values())


def event_kind(kind_id: str) -> EventKindDef | None:
    return next((k for k in event_kinds() if k.id == kind_id), None)


# ------------------------------------------------------------------ daily prompts & panels

DAILY_PROMPTS_BY_ID: dict[str, DailyPromptDef] = {p.id: p for p in DAILY_PROMPTS}


def daily_prompts_for(market: str) -> list[DailyPromptDef]:
    return [p for p in DAILY_PROMPTS if market in p.markets]


PANELS_BY_ID: dict[str, PanelDef] = {p.id: p for p in PANELS}


def panels_for(market: str) -> list[PanelDef]:
    """Every panel, made-for-this-market first (a US user can still try an Indian GD)."""
    return sorted(PANELS, key=lambda p: relevance(p.markets, market))
