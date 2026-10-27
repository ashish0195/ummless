"""Event kinds offered when adding an upcoming moment to prepare for (POST /v1/events).

Ids match the EventKind enum in docs/API.md. `prep_hint` guides the model that builds three prep items for the
event; it names the three moments most worth rehearsing for that kind of event.
"""

from __future__ import annotations

from .schema import EventKindDef

_ALL = ("us", "in", "global")

EVENT_KINDS: tuple[EventKindDef, ...] = (
    # ------------------------------------------------------------------ seed entries (used by tests)
    EventKindDef(id="interview", title="Job interview", symbol="person.crop.rectangle", markets=("us", "in", "global"),
                 prep_hint="Tell me about yourself, one behavioural story (STAR), a tough 'why should we hire you', "
                 "and a question to ask them."),
    EventKindDef(id="placement", title="Campus placement", symbol="graduationcap", markets=("in",),
                 prep_hint="HR round introduction, 'why this company', a project explanation for a technical panel, "
                 "and relocation or bond questions."),
    EventKindDef(id="group_discussion", title="Group discussion", symbol="person.3", markets=("in",),
                 prep_hint="Entering the GD with a clear opening point, building on others, and summarising."),
    # ------------------------------------------------------------------ the rest
    EventKindDef(id="client_call", title="Client call", symbol="phone", markets=_ALL,
                 prep_hint="Opening the call with a one-line agenda, explaining an issue or a delay in plain English "
                 "with a fix date, and calming an unhappy or demanding client, including across time zones."),
    EventKindDef(id="viva", title="Viva or project defence", symbol="studentdesk", markets=("in",),
                 prep_hint="Explaining the project's problem and approach in simple terms, defending one design "
                 "choice under questioning, and admitting what you'd improve without sounding defensive."),
    EventKindDef(id="appraisal", title="Appraisal or performance review", symbol="chart.line.uptrend.xyaxis",
                 markets=_ALL,
                 prep_hint="Making the case for your rating with two or three measurable results, responding to "
                 "critical feedback without getting defensive, and asking for a raise or promotion with a specific "
                 "number."),
    EventKindDef(id="meeting", title="Important meeting", symbol="person.2", markets=_ALL,
                 prep_hint="Leading with your recommendation, a three-part status update (where we are, the risk, "
                 "what I need), and handling pushback from a senior stakeholder."),
    EventKindDef(id="presentation", title="Presentation or talk", symbol="chart.bar.doc.horizontal", markets=_ALL,
                 prep_hint="A strong opening hook with a one-line preview, landing the key number with a pause, and "
                 "answering a tough audience question."),
    EventKindDef(id="negotiation", title="Negotiation", symbol="scalemass", markets=_ALL,
                 prep_hint="Anchoring with a specific number and a reason, asking about the other side's "
                 "constraints, and closing with a clear summary of what was agreed."),
    EventKindDef(id="social", title="Social event", symbol="party.popper", markets=_ALL,
                 prep_hint="Introducing yourself in a way that invites conversation, asking follow-up questions "
                 "about specific details, and telling a short story with a turning point."),
    EventKindDef(id="other", title="Something else", symbol="calendar", markets=_ALL,
                 prep_hint="Rehearsing the most likely opening moment, the hardest question or objection you "
                 "expect, and how you want to close."),
)
