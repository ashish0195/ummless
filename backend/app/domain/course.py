"""Course content: 5 goal tracks × 4 modules × 4 missions (the spec's weekly rhythm).

Each module has ONE observable target behavior, a short example, and three conversations-worth of
practice: Learn & try (AI partner raises one realistic objection), Remix (same skill, different person or
situation), Real-life mission (with an AI alternative), and a Weekly reveal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

TRACKS: dict[str, dict[str, str]] = {
    "negotiation": {
        "title": "Negotiation",
        "subtitle": "Ask for what you want and handle pushback.",
        "symbol": "scalemass",
    },
    "business": {
        "title": "Business communication",
        "subtitle": "Make your point land in meetings and updates.",
        "symbol": "briefcase",
    },
    "conversational": {
        "title": "Conversational communication",
        "subtitle": "Easier, warmer everyday conversations.",
        "symbol": "bubble.left.and.bubble.right",
    },
    "storytelling": {
        "title": "Storytelling",
        "subtitle": "Turn experiences into stories people remember.",
        "symbol": "book",
    },
    "public_speaking": {
        "title": "Public communication",
        "subtitle": "Speak to a room with clarity and calm.",
        "symbol": "megaphone",
    },
}

TRACK_ORDER = ("business", "interviews", "negotiation", "conversational", "storytelling", "public_speaking")


@dataclass(frozen=True)
class PartnerDef:
    name: str
    role: str
    voice: str
    symbol: str
    color_hex: str
    character: str
    opening: str
    follow_up: str  # instruction for the partner's one follow-up/objection after the first attempt
    follow_up_fallback: str
    tts_instructions: str = (
        "Voice: natural and conversational. Tone: realistic for the role. Pace: everyday speech, never an announcer."
    )


@dataclass(frozen=True)
class MissionDef:
    id: str
    module_id: str
    track_id: str
    type: str
    title: str
    minutes: int
    context: str
    suggested_seconds: int
    steps: tuple[str, ...]
    partner: PartnerDef | None = None
    real_life_prompt: str | None = None
    ai_alternative_title: str | None = None
    reflection_questions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModuleDef:
    id: str
    track_id: str
    index: int
    title: str
    dimension: str
    target_behavior: str
    summary: str
    why_it_matters: str
    example_text: str
    example_explanation: str
    missions: tuple[MissionDef, ...]

    def mission(self, mission_type: str) -> MissionDef:
        return next(m for m in self.missions if m.type == mission_type)


def _partner(data: dict[str, Any]) -> PartnerDef:
    return PartnerDef(
        name=data["name"],
        role=data["role"],
        voice=data.get("voice", "marin"),
        symbol=data.get("symbol", "person.wave.2"),
        color_hex=data.get("color", "#5146E6"),
        character=data.get("character", f"{data['name']}, {data['role'].lower()}."),
        opening=data["opening"],
        follow_up=data["follow_up"],
        follow_up_fallback=data["fallback"],
        tts_instructions=data.get("tts_instructions") or PartnerDef.tts_instructions,
    )


def _module(track_id: str, index: int, spec: dict[str, Any]) -> ModuleDef:
    module_id = f"{track_id}.m{index}"
    target = spec["target"]
    learn_partner = _partner(spec["learn"]["partner"])
    remix_partner = _partner(spec["remix"]["partner"])
    alt_partner = _partner(spec["real"]["partner"])
    missions = (
        MissionDef(
            id=f"{module_id}.learn",
            module_id=module_id,
            track_id=track_id,
            type="learn_and_try",
            title=spec["title"],
            minutes=6,
            context=spec["learn"]["context"],
            suggested_seconds=spec.get("seconds", 60),
            steps=(
                "Read the target and listen to the example.",
                f"{learn_partner.name} starts the conversation — answer with the target in mind.",
                f"{learn_partner.name} will respond once, maybe with an objection. Adapt.",
                "Get feedback on where the target showed up. Try again if you like.",
            ),
            partner=learn_partner,
        ),
        MissionDef(
            id=f"{module_id}.remix",
            module_id=module_id,
            track_id=track_id,
            type="remix",
            title=spec["remix"].get("title", f"Remix: {spec['title'].lower()}"),
            minutes=5,
            context=spec["remix"]["context"],
            suggested_seconds=spec.get("seconds", 60),
            steps=(
                "Same skill, new person and situation.",
                f"{remix_partner.name} starts — aim for the same target.",
                "See whether the skill transfers beyond a memorized answer.",
            ),
            partner=remix_partner,
        ),
        MissionDef(
            id=f"{module_id}.real",
            module_id=module_id,
            track_id=track_id,
            type="real_life",
            title=spec["real"].get("title", "Real-life mission"),
            minutes=10,
            context=spec["real"]["prompt"],
            suggested_seconds=spec.get("seconds", 60),
            steps=(
                "Use the target in a real conversation this week.",
                "Afterwards, reflect on what happened (or add a permitted recording).",
                "Can't find a moment? Try the AI alternative instead.",
            ),
            partner=alt_partner,
            real_life_prompt=spec["real"]["prompt"],
            ai_alternative_title=spec["real"]["alt_title"],
            reflection_questions=tuple(spec["real"]["questions"]),
        ),
        MissionDef(
            id=f"{module_id}.reveal",
            module_id=module_id,
            track_id=track_id,
            type="weekly_reveal",
            title="Weekly reveal",
            minutes=3,
            context="Look back at this week's attempts and reflections, see what changed, and choose your next focus.",
            suggested_seconds=0,
            steps=(
                "Review your attempts, reflections and any new recordings.",
                "Compare a before and an after against the same target.",
                "Choose next week's focus.",
            ),
        ),
    )
    return ModuleDef(
        id=module_id,
        track_id=track_id,
        index=index,
        title=spec["title"],
        dimension=spec["dimension"],
        target_behavior=target,
        summary=spec["summary"],
        why_it_matters=spec["why"],
        example_text=spec["example"],
        example_explanation=spec["example_explanation"],
        missions=missions,
    )


_CONTENT: dict[str, list[dict[str, Any]]] = {
    "business": [
        {
            "title": "Make your point land",
            "dimension": "concision",
            "target": "State your recommendation first, give two relevant reasons, then invite a response.",
            "summary": "Lead with your recommendation so nobody has to dig for it.",
            "why": "Attention drops fast in meetings. Leading with the recommendation means people hear it even if "
            "they tune out halfway.",
            "example": "\"I'd go with the Lisbon vendor. They're 20% cheaper, and they've already passed our "
            "security review. What would you want covered before we sign?\"",
            "example_explanation": "Recommendation in the first sentence, two reasons that matter to the decision, "
            "then an invitation to respond.",
            "learn": {
                "context": "Your project team asks which of two vendors to choose: a cheaper new one, or the "
                "familiar, pricier one.",
                "partner": {
                    "name": "Jordan", "role": "Teammate", "voice": "ash", "symbol": "person.2", "color": "#6366F1",
                    "character": "Jordan, a thoughtful teammate who leans toward the familiar vendor.",
                    "opening": "So, we need to pick a vendor by Friday. Which one do you think we should go with?",
                    "follow_up": "Raise ONE reasonable objection to their recommendation — the risk of switching, "
                    "onboarding time, or why the other option feels safer. Two sentences at most.",
                    "fallback": "I hear you, but switching vendors mid-quarter feels risky. What if onboarding "
                    "takes longer than we think?",
                },
            },
            "remix": {
                "title": "Remix: the hallway question",
                "context": "Your manager stops you in the hallway: should the team delay the launch by a week?",
                "partner": {
                    "name": "Elena", "role": "Your manager", "voice": "sage", "symbol": "figure.walk",
                    "color": "#2F9BFF",
                    "opening": "Hey, quick one. Should we push the launch back a week? Just give me your take.",
                    "follow_up": "Push back once by naming a cost of their recommendation — sales already promised "
                    "the date, or a risk they're downplaying.",
                    "fallback": "Sales already promised two customers it's the 14th, though. Does that change "
                    "your answer?",
                },
            },
            "real": {
                "prompt": "In your next meeting, when someone asks for your view, say your recommendation in your "
                "first sentence — before any background.",
                "alt_title": "No meeting soon? Give your recommendation to an AI skip-level manager.",
                "partner": {
                    "name": "Grace", "role": "Skip-level manager", "voice": "shimmer", "symbol": "person.crop.square",
                    "color": "#9B5DE5",
                    "opening": "I've got five minutes. Should we hire a contractor now or wait for the full-time "
                    "role? What's your recommendation?",
                    "follow_up": "Ask one sharp question about the downside of their recommendation.",
                    "fallback": "What's the biggest risk with that, and how would you handle it?",
                },
                "questions": ["What did you say first?", "How did people respond?", "What would you change next time?"],
            },
        },
        {
            "title": "Give an update people can follow",
            "dimension": "structure",
            "target": "Give a three-part update: where things stand, what's at risk, and what you need.",
            "summary": "A predictable shape makes your update easy to follow and act on.",
            "why": "Updates often ramble through every detail. A fixed shape lets listeners find the part they "
            "care about.",
            "example": "\"Where we are: the beta is live with 40 users. The risk: two enterprise clients need SSO "
            "before they'll join. What I need: a decision this week on whether SSO goes into the next sprint.\"",
            "example_explanation": "Three signposts — where we are, the risk, what I need — that listeners can "
            "hold onto.",
            "seconds": 75,
            "learn": {
                "context": "It's the weekly check-in. Your director asks for an update on your main project.",
                "partner": {
                    "name": "Nadia", "role": "Director", "voice": "shimmer", "symbol": "chart.bar",
                    "color": "#9B5DE5",
                    "opening": "Okay, give me the quick version. Where are we on your project?",
                    "follow_up": "Ask for the one thing they left vague: a date, a number, or exactly what they "
                    "need from you.",
                    "fallback": "When you say 'soon', what date should I tell my boss?",
                },
            },
            "remix": {
                "title": "Remix: the worried client",
                "context": "A worried client calls to ask whether their delivery is still on track.",
                "partner": {
                    "name": "Tom", "role": "Client", "voice": "echo", "symbol": "phone", "color": "#FF8A3D",
                    "opening": "I'm getting nervous. Are we still on track for the end of the month?",
                    "follow_up": "Express worry about one risk they mentioned and ask what happens if it goes wrong.",
                    "fallback": "And if that risk does happen, what's the backup plan?",
                },
            },
            "real": {
                "prompt": "In your next standup or status update, use the three parts: where we are, the risk, "
                "what I need.",
                "alt_title": "Give a status update to an AI director instead.",
                "partner": {
                    "name": "Nadia", "role": "Director", "voice": "shimmer", "symbol": "chart.bar",
                    "color": "#9B5DE5",
                    "opening": "Quick status on the hiring plan? Where are we?",
                    "follow_up": "Ask what exactly they need from you.",
                    "fallback": "So what exactly do you need from me?",
                },
                "questions": ["Did you name a risk out loud?", "Did you get what you asked for?",
                              "What would you cut next time?"],
            },
        },
        {
            "title": "Handle pushback calmly",
            "dimension": "persuasion",
            "target": "When challenged, acknowledge the concern, answer it with one specific fact, then restate "
            "your ask.",
            "summary": "Turn objections into reasons to agree — without getting defensive.",
            "why": "Pushback means someone is engaging. A calm acknowledge–answer–ask pattern keeps the "
            "conversation moving toward yes.",
            "example": "\"That's a fair worry about cost. The pilot is $8k, and it replaces a $30k contract if it "
            "works. So I'm asking for a yes on the pilot only.\"",
            "example_explanation": "Acknowledges the concern, answers with one specific fact, and restates a "
            "smaller ask.",
            "learn": {
                "context": "You're asking a budget holder for $15k to run a pilot. They're not convinced.",
                "partner": {
                    "name": "Helen", "role": "Budget holder", "voice": "sage", "symbol": "dollarsign.circle",
                    "color": "#E64980",
                    "opening": "I've read your proposal. Honestly, I don't see why we'd spend fifteen thousand on "
                    "this right now.",
                    "follow_up": "Raise a second, sharper objection — for example, that you tried something "
                    "similar before and it failed.",
                    "fallback": "We tried something similar two years ago and it went nowhere. Why is this "
                    "different?",
                },
            },
            "remix": {
                "title": "Remix: pushback in the room",
                "context": "A peer disagrees with your plan in front of the team.",
                "partner": {
                    "name": "Ravi", "role": "Peer in a meeting", "voice": "ash", "symbol": "person.3",
                    "color": "#10B3A3",
                    "opening": "I'm going to push back here. I think this plan is too ambitious for one quarter.",
                    "follow_up": "Push back once more with a specific concern about workload.",
                    "fallback": "My team is already at capacity. Who's actually doing the extra work?",
                },
            },
            "real": {
                "prompt": "Next time someone pushes back on you, try: acknowledge, one specific fact, restate "
                "your ask.",
                "alt_title": "Practice with an AI budget holder who isn't convinced.",
                "partner": {
                    "name": "Helen", "role": "Budget holder", "voice": "sage", "symbol": "dollarsign.circle",
                    "color": "#E64980",
                    "opening": "I'm not convinced we need another hire this year. Convince me.",
                    "follow_up": "Raise one objection about cost.",
                    "fallback": "That's another salary we honestly can't afford right now.",
                },
                "questions": ["What was the objection?", "Did you acknowledge it before answering?",
                              "How did they respond?"],
            },
        },
        {
            "title": "Bring others in",
            "dimension": "listening",
            "target": "After you speak, ask one specific question and build on the answer before adding your view.",
            "summary": "Meetings aren't won by talking most. Draw out what others know.",
            "why": "People commit to decisions they helped shape, and asking surfaces information you'd otherwise "
            "miss.",
            "example": "\"Lin, you've seen the support tickets — what are customers actually complaining about? … "
            "So it's the export step. Then I think we fix that before adding features.\"",
            "example_explanation": "A specific question to a specific person, then building on their answer.",
            "learn": {
                "context": "You're brainstorming with a quiet colleague who knows more than they've said.",
                "partner": {
                    "name": "Lin", "role": "Quiet colleague", "voice": "coral", "symbol": "person.fill.questionmark",
                    "color": "#10B3A3",
                    "character": "Lin, an analyst who rarely speaks up but has seen the customer data.",
                    "opening": "I'm not sure I have much to add… what were you thinking for the launch plan?",
                    "follow_up": "Share one useful piece of information hesitantly — for example that support has "
                    "seen lots of complaints about exports — and see whether they build on it.",
                    "fallback": "Well… support has been getting a lot of complaints about the export step. Not sure "
                    "if that matters.",
                },
            },
            "remix": {
                "title": "Remix: the one-to-one",
                "context": "A one-to-one with a direct report who seems disengaged.",
                "partner": {
                    "name": "Chris", "role": "Direct report", "voice": "echo",
                    "symbol": "person.crop.circle.badge.questionmark", "color": "#FF8A3D",
                    "opening": "Everything's fine, I guess. Just a lot going on.",
                    "follow_up": "Give a vague answer that hints at the real issue (unclear priorities) and see if "
                    "they follow up.",
                    "fallback": "It's just… I never know which project is actually the priority.",
                },
            },
            "real": {
                "prompt": "In your next meeting, ask one person a specific question and build on their answer "
                "before giving your view.",
                "alt_title": "Draw out a quiet AI colleague instead.",
                "partner": {
                    "name": "Lin", "role": "Quiet colleague", "voice": "coral", "symbol": "person.fill.questionmark",
                    "color": "#10B3A3",
                    "opening": "Hi — sorry I've been quiet in these meetings. What did you want to talk about?",
                    "follow_up": "Share a hesitant idea and see whether they explore it.",
                    "fallback": "I did have one idea about the onboarding emails, but it's probably nothing.",
                },
                "questions": ["Who did you ask, and what?", "What did you learn that you didn't know?",
                              "Did it change your view?"],
            },
        },
    ],
    "negotiation": [
        {
            "title": "Anchor with a reason",
            "dimension": "persuasion",
            "target": "Name a specific number first, and give one reason it's fair.",
            "summary": "The first concrete number shapes the whole negotiation.",
            "why": "Vague asks invite low offers. A specific number with a reason gives the other side something "
            "real to respond to.",
            "example": "\"I'm looking for 135. That's in line with market data for this scope, and I'm bringing "
            "the payments experience you said you need.\"",
            "example_explanation": "A specific number, then a reason tied to what they value.",
            "learn": {
                "context": "A hiring manager asks for your salary expectations.",
                "partner": {
                    "name": "Daniel", "role": "Hiring manager", "voice": "echo", "symbol": "briefcase",
                    "color": "#9B5DE5",
                    "opening": "Before we go further, what salary range are you looking for?",
                    "follow_up": "Push back on their number once (budget constraints) and see whether they hold "
                    "their anchor and justify it.",
                    "fallback": "That's above what we budgeted. Is there any flexibility there?",
                },
            },
            "remix": {
                "title": "Remix: your freelance rate",
                "context": "A prospective client asks what you'd charge for a project.",
                "partner": {
                    "name": "Sofia", "role": "Prospective client", "voice": "shimmer", "symbol": "doc.text",
                    "color": "#2F9BFF",
                    "opening": "We love your portfolio. What would you charge for the redesign?",
                    "follow_up": "Say another freelancer quoted about 30% less and ask why you're worth more.",
                    "fallback": "We had another quote that was about thirty percent lower. Why should we pay more?",
                },
            },
            "real": {
                "prompt": "Next time you set a price, rate or ask, say the specific number first, plus one reason "
                "it's fair.",
                "alt_title": "Quote your rate to an AI client instead.",
                "partner": {
                    "name": "Sofia", "role": "Prospective client", "voice": "shimmer", "symbol": "doc.text",
                    "color": "#2F9BFF",
                    "opening": "So what's your day rate for this kind of work?",
                    "follow_up": "Push back once on the price.",
                    "fallback": "Hmm, that's more than we expected to spend.",
                },
                "questions": ["What number did you name?", "What reason did you give?", "Where did you land?"],
            },
        },
        {
            "title": "Ask, then listen",
            "dimension": "listening",
            "target": "Ask an open question about their constraints, and summarize what you heard before you "
            "respond.",
            "summary": "Find out what the other side actually needs before you counter.",
            "why": "Deals stall on unspoken constraints. Summarizing proves you heard them and often reveals room "
            "to trade.",
            "example": "\"What's driving the increase on your side? … So taxes went up and the boiler needs "
            "replacing — it's mostly about covering costs this year. Is that right?\"",
            "example_explanation": "An open question, then a summary that checks understanding before countering.",
            "learn": {
                "context": "Your landlord announces a rent increase at renewal.",
                "partner": {
                    "name": "Rosa", "role": "Landlord", "voice": "shimmer", "symbol": "house", "color": "#2F9BFF",
                    "character": "Rosa owns four apartments; her taxes and repair costs rose. She hates vacancies.",
                    "opening": "I wanted to let you know the rent is going up twelve percent when your lease renews.",
                    "follow_up": "If they asked about your reasons, explain them (taxes, a new boiler) and mention "
                    "you'd hate a vacancy. If they didn't ask, stay firm and vague.",
                    "fallback": "Property taxes went up, and the boiler needs replacing. I can't just absorb that.",
                },
            },
            "remix": {
                "title": "Remix: the vendor renewal",
                "context": "A vendor wants to raise their contract price at renewal.",
                "partner": {
                    "name": "Mark", "role": "Vendor account manager", "voice": "ash", "symbol": "building.2",
                    "color": "#E64980",
                    "opening": "Our renewal pricing is going up eighteen percent this year. I hope that works.",
                    "follow_up": "Explain your reasons only if asked (new compliance costs); otherwise repeat the "
                    "number politely.",
                    "fallback": "Our compliance costs went up a lot this year, so that's where it comes from.",
                },
            },
            "real": {
                "prompt": "In your next negotiation or disagreement, ask one open question about their side and "
                "summarize it before you answer.",
                "alt_title": "Negotiate with an AI landlord instead.",
                "partner": {
                    "name": "Rosa", "role": "Landlord", "voice": "shimmer", "symbol": "house", "color": "#2F9BFF",
                    "opening": "The rent is going up next month. I've sent the new lease.",
                    "follow_up": "Explain your constraints only if they ask.",
                    "fallback": "My costs went up across the board this year.",
                },
                "questions": ["What did you learn about their constraints?", "Did you summarize before countering?",
                              "Did it change the outcome?"],
            },
        },
        {
            "title": "Say no without over-explaining",
            "dimension": "concision",
            "target": "Decline in one clear sentence with one reason, then offer an alternative.",
            "summary": "A short, kind no is easier to hear than a long apology.",
            "why": "Over-explaining sounds unsure and invites more pushing. One reason plus an alternative stays "
            "respectful and firm.",
            "example": "\"I can't take on the event this month — I'm at capacity with the launch. I could help plan "
            "the next one in March.\"",
            "example_explanation": "One clear no, one reason, one alternative. No apology spiral.",
            "seconds": 45,
            "learn": {
                "context": "A colleague asks you to take over an extra project you don't have time for.",
                "partner": {
                    "name": "Ben", "role": "Colleague", "voice": "echo", "symbol": "tray.full", "color": "#FF8A3D",
                    "opening": "Hey, could you take over the partner newsletter? It's only a few hours a week.",
                    "follow_up": "Push once more, a little guilt-trippy: it would really help, nobody else can do it.",
                    "fallback": "It'd really help me out. Honestly, nobody else can do it.",
                },
            },
            "remix": {
                "title": "Remix: a friend's favor",
                "context": "A friend asks to borrow a significant amount of money.",
                "partner": {
                    "name": "Jess", "role": "Friend", "voice": "coral", "symbol": "heart.circle", "color": "#10B3A3",
                    "opening": "This is awkward, but could you lend me two thousand until next month?",
                    "follow_up": "Push gently: promise to pay it back.",
                    "fallback": "I'd pay you back, I promise. It's just this month.",
                },
            },
            "real": {
                "prompt": "The next time you need to say no, use one sentence, one reason and one alternative.",
                "alt_title": "Say no to an AI colleague's request instead.",
                "partner": {
                    "name": "Ben", "role": "Colleague", "voice": "echo", "symbol": "tray.full", "color": "#FF8A3D",
                    "opening": "Can you cover my on-call shift this weekend?",
                    "follow_up": "Push once more.",
                    "fallback": "Are you sure? It's just this one time.",
                },
                "questions": ["How many sentences did your no take?", "Did you offer an alternative?",
                              "How did it feel?"],
            },
        },
        {
            "title": "Close warmly",
            "dimension": "warmth",
            "target": "Summarize the agreement, name one thing you appreciated, and confirm the next step.",
            "summary": "End negotiations so both sides want to work together again.",
            "why": "How a negotiation ends shapes the relationship. A warm, clear close prevents misunderstandings "
            "and builds goodwill.",
            "example": "\"So we're agreed: 128 base, starting on the 3rd, with a review in six months. I really "
            "appreciated you going back to HR for me. I'll sign tonight.\"",
            "example_explanation": "Summary, appreciation, next step — three short beats.",
            "seconds": 45,
            "learn": {
                "context": "You've just agreed terms with a hiring manager. Close the conversation.",
                "partner": {
                    "name": "Daniel", "role": "Hiring manager", "voice": "echo", "symbol": "briefcase",
                    "color": "#9B5DE5",
                    "opening": "Okay, I think we can do one-twenty-eight with the March start. Are we good?",
                    "follow_up": "Mention one detail they didn't confirm (the six-month review) to see if they "
                    "confirm it clearly.",
                    "fallback": "Oh, and we didn't talk about the six-month review. Does that still work for you?",
                },
            },
            "remix": {
                "title": "Remix: closing with your landlord",
                "context": "You and your landlord have agreed on a smaller increase.",
                "partner": {
                    "name": "Rosa", "role": "Landlord", "voice": "shimmer", "symbol": "house", "color": "#2F9BFF",
                    "opening": "Fine. Five percent, and you sign for two years. Deal?",
                    "follow_up": "Ask a practical follow-up (when they'll sign, how payment changes).",
                    "fallback": "Good. When can you sign the new lease?",
                },
            },
            "real": {
                "prompt": "At the end of your next agreement — big or small — summarize it, thank them for one "
                "specific thing, and confirm the next step.",
                "alt_title": "Close a deal with an AI hiring manager instead.",
                "partner": {
                    "name": "Daniel", "role": "Hiring manager", "voice": "echo", "symbol": "briefcase",
                    "color": "#9B5DE5",
                    "opening": "Alright, we can meet you at your number. Anything else before I send the paperwork?",
                    "follow_up": "Ask when they can start.",
                    "fallback": "Great. When could you start?",
                },
                "questions": ["What did you summarize?", "What did you thank them for?",
                              "Was the next step clear to both of you?"],
            },
        },
    ],
    "conversational": [
        {
            "title": "Ask the second question",
            "dimension": "listening",
            "target": "Ask a follow-up question about a specific detail the other person mentioned.",
            "summary": "The second question is where real conversations start.",
            "why": "First questions are polite; follow-ups prove you were listening. People remember feeling heard.",
            "example": "\"You said you just got back from Lisbon — what surprised you most about it?\"",
            "example_explanation": "References a specific detail and asks something open about it.",
            "seconds": 45,
            "learn": {
                "context": "You meet someone new at a friend's birthday.",
                "partner": {
                    "name": "Theo", "role": "New acquaintance", "voice": "verse", "symbol": "party.popper",
                    "color": "#10B3A3",
                    "opening": "Hi! I'm Theo, I know the birthday girl from my climbing gym. I just got back from a "
                    "trip, so I'm still a bit jet-lagged.",
                    "follow_up": "Answer their question with one or two specific details, including something they "
                    "could follow up on (you tried surfing for the first time and were terrible).",
                    "fallback": "Yeah, two weeks in Portugal. I tried surfing for the first time and was "
                    "hilariously bad at it.",
                },
            },
            "remix": {
                "title": "Remix: the coffee machine",
                "context": "Small talk with a colleague you don't know well, at the coffee machine.",
                "partner": {
                    "name": "Amara", "role": "Colleague from another team", "voice": "coral",
                    "symbol": "cup.and.saucer", "color": "#FF8A3D",
                    "opening": "Morning! Long week already — we've been moving offices on our floor.",
                    "follow_up": "Answer with a specific detail they could follow up on.",
                    "fallback": "Best part, we finally get windows. Worst part, I lost my favorite desk plant in "
                    "the move.",
                },
            },
            "real": {
                "prompt": "In your next casual conversation, ask at least one follow-up about something specific "
                "the other person said.",
                "alt_title": "Make small talk with an AI at a party instead.",
                "partner": {
                    "name": "Theo", "role": "New acquaintance", "voice": "verse", "symbol": "party.popper",
                    "color": "#10B3A3",
                    "opening": "Hey, I don't think we've met. I'm Theo — I just started learning pottery, which is "
                    "going terribly.",
                    "follow_up": "Answer with a detail they could follow up on.",
                    "fallback": "My first bowl looked like an ashtray. My friends now use it as an ashtray.",
                },
                "questions": ["What follow-up did you ask?", "What did you learn?",
                              "How did the conversation change after it?"],
            },
        },
        {
            "title": "Share, then pass the ball",
            "dimension": "warmth",
            "target": "Share something about yourself in two or three sentences, then hand the conversation back "
            "with a question.",
            "summary": "Conversations are a rally, not a speech.",
            "why": "Sharing makes you relatable; passing the ball back makes the other person feel included.",
            "example": "\"I've been learning to make dumplings — badly, but my folding is improving. Do you cook "
            "much?\"",
            "example_explanation": "A short, specific share, then an easy question back.",
            "seconds": 45,
            "learn": {
                "context": "On a first coffee with someone new, they ask about you.",
                "partner": {
                    "name": "Alex", "role": "First coffee", "voice": "coral", "symbol": "cup.and.saucer",
                    "color": "#10B3A3",
                    "opening": "So tell me something about you that's not on your profile.",
                    "follow_up": "Respond warmly to what they shared, answer their question if they asked one, and "
                    "share something small about yourself.",
                    "fallback": "Ha, I love that. I've been trying to learn guitar, but my neighbors probably hate me.",
                },
            },
            "remix": {
                "title": "Remix: the new teammate",
                "context": "A new teammate asks what you do outside work.",
                "partner": {
                    "name": "Kai", "role": "New teammate", "voice": "ash", "symbol": "person.badge.plus",
                    "color": "#2F9BFF",
                    "opening": "So what do you get up to outside work?",
                    "follow_up": "Respond to what they shared and answer any question they asked.",
                    "fallback": "Oh nice! I'm mostly hiking on weekends — trying to do every trail in the state.",
                },
            },
            "real": {
                "prompt": "In your next conversation, share something real in two or three sentences, then ask a "
                "question back.",
                "alt_title": "Have a first coffee with an AI instead.",
                "partner": {
                    "name": "Alex", "role": "First coffee", "voice": "coral", "symbol": "cup.and.saucer",
                    "color": "#10B3A3",
                    "opening": "So what's been the best part of your week?",
                    "follow_up": "Respond warmly and share something of your own.",
                    "fallback": "That sounds great. Mine was finally finishing a puzzle I've been doing for a month.",
                },
                "questions": ["What did you share?", "What did you ask back?", "Did the conversation keep going?"],
            },
        },
        {
            "title": "Keep it short and vivid",
            "dimension": "concision",
            "target": "Answer \"what have you been up to?\" in under 30 seconds, with one specific detail.",
            "summary": "One vivid detail beats a list of everything.",
            "why": "Long recaps lose listeners. One specific detail gives the other person something to latch onto.",
            "example": "\"Mostly work, but the highlight was fixing up my old bike — I rode to the coast on Sunday "
            "and got caught in hail.\"",
            "example_explanation": "Short, one concrete detail, and an easy hook for a follow-up.",
            "seconds": 30,
            "learn": {
                "context": "An old friend you haven't seen in months asks what you've been up to.",
                "partner": {
                    "name": "Jamie", "role": "Old friend", "voice": "verse", "symbol": "person.2", "color": "#FF8A3D",
                    "opening": "It's been ages! What have you been up to?",
                    "follow_up": "Follow up on their most specific detail with genuine curiosity.",
                    "fallback": "Wait, really? How did that happen?",
                },
            },
            "remix": {
                "title": "Remix: \"so, what do you do?\"",
                "context": "At a networking event, someone asks what you do.",
                "partner": {
                    "name": "Morgan", "role": "Event attendee", "voice": "sage",
                    "symbol": "person.crop.rectangle.stack", "color": "#2F9BFF",
                    "opening": "So, what do you do?",
                    "follow_up": "Ask a curious follow-up about the most interesting thing they said.",
                    "fallback": "Interesting. What's the part of that you enjoy most?",
                },
            },
            "real": {
                "prompt": "Next time someone asks what you've been up to, answer in under 30 seconds with one "
                "vivid detail.",
                "alt_title": "Catch up with an AI friend instead.",
                "partner": {
                    "name": "Jamie", "role": "Old friend", "voice": "verse", "symbol": "person.2", "color": "#FF8A3D",
                    "opening": "Hey stranger! What's new with you?",
                    "follow_up": "Follow up on one detail.",
                    "fallback": "No way. Tell me more about that.",
                },
                "questions": ["What detail did you pick?", "Did they ask about it?", "What would you leave out next time?"],
            },
        },
        {
            "title": "Tell a quick story",
            "dimension": "storytelling",
            "target": "Tell a 60-second story with a clear moment where something changed.",
            "summary": "Short stories make you memorable in everyday conversation.",
            "why": "Stories with a turning point are how people connect and remember each other.",
            "example": "\"I was sure I'd missed my flight — then the agent glanced at my ticket and said, 'You're "
            "Gate B, this is A.' I sprinted, made it, and the whole plane clapped.\"",
            "example_explanation": "A setup, a turn and a payoff — all in under a minute.",
            "seconds": 75,
            "learn": {
                "context": "At dinner, a friend asks about the funniest thing that happened to you this year.",
                "partner": {
                    "name": "Nina", "role": "Friend at dinner", "voice": "coral", "symbol": "fork.knife",
                    "color": "#9B5DE5",
                    "opening": "Okay, what's the funniest thing that's happened to you this year?",
                    "follow_up": "React to the story and ask what happened next, or how it ended.",
                    "fallback": "No way. So what happened after that?",
                },
            },
            "remix": {
                "title": "Remix: Monday morning",
                "context": "A colleague asks how your weekend went.",
                "partner": {
                    "name": "Sam", "role": "Colleague", "voice": "ash", "symbol": "sun.horizon", "color": "#FF8A3D",
                    "opening": "Morning! How was your weekend?",
                    "follow_up": "React and ask about the most interesting moment.",
                    "fallback": "Ha! Then what?",
                },
            },
            "real": {
                "prompt": "Tell a short story with a turning point to someone this week — at dinner, on a call, "
                "anywhere.",
                "alt_title": "Tell your story to an AI friend instead.",
                "partner": {
                    "name": "Nina", "role": "Friend", "voice": "coral", "symbol": "fork.knife", "color": "#9B5DE5",
                    "opening": "Tell me something that surprised you recently.",
                    "follow_up": "Ask what happened next.",
                    "fallback": "And then what happened?",
                },
                "questions": ["Where was the turning point?", "How did they react?", "What would you cut?"],
            },
        },
    ],
    "storytelling": [
        {
            "title": "Start in the moment",
            "dimension": "storytelling",
            "target": "Open your story at a specific moment — a time, a place, an action — not with background.",
            "summary": "Drop the listener into the scene from the first sentence.",
            "why": "Background-first openings lose people. Starting in the moment creates instant curiosity.",
            "example": "\"It's 2 a.m., I'm in a hospital parking lot, and I realize I've locked my keys in the car — "
            "with the engine running.\"",
            "example_explanation": "Time, place and action in the first sentence. Background can come later, if at all.",
            "seconds": 75,
            "learn": {
                "context": "A friend asks how you ended up in your current job.",
                "partner": {
                    "name": "Ivy", "role": "Friend", "voice": "coral", "symbol": "sparkles", "color": "#9B5DE5",
                    "opening": "How did you actually end up doing what you do now?",
                    "follow_up": "Ask them to go back to one specific moment in their story: what was that moment "
                    "like?",
                    "fallback": "Wait, go back — what was that moment actually like?",
                },
            },
            "remix": {
                "title": "Remix: the interview story",
                "context": "An interviewer asks you to describe a challenge you faced at work.",
                "partner": {
                    "name": "Priya", "role": "Interviewer", "voice": "sage", "symbol": "person.crop.rectangle",
                    "color": "#6366F1",
                    "opening": "Tell me about a challenge you faced at work and how you handled it.",
                    "follow_up": "Ask what they personally did at the hardest moment.",
                    "fallback": "And what did you personally do at that point?",
                },
            },
            "real": {
                "prompt": "Tell a story this week whose first sentence is a moment: a time, a place, an action.",
                "alt_title": "Tell an AI friend a story instead.",
                "partner": {
                    "name": "Ivy", "role": "Friend", "voice": "coral", "symbol": "sparkles", "color": "#9B5DE5",
                    "opening": "Tell me about a moment you'll never forget.",
                    "follow_up": "Ask about one detail.",
                    "fallback": "What do you remember most clearly about it?",
                },
                "questions": ["What was your first sentence?", "Did they lean in?", "What background did you cut?"],
            },
        },
        {
            "title": "Build to a turn",
            "dimension": "structure",
            "target": "Give your story a setup, a turning point, and what changed.",
            "summary": "Every good story has a moment where something shifts.",
            "why": "Without a turn, a story is just a list of events. The turn is what makes it worth telling.",
            "example": "\"I'd prepared for weeks. Five minutes in, the projector died. I put the slides away and just "
            "talked — and it was the best talk I've ever given.\"",
            "example_explanation": "Setup, turn, change — three beats listeners can follow.",
            "seconds": 90,
            "learn": {
                "context": "A colleague asks about a project that surprised you.",
                "partner": {
                    "name": "Omar", "role": "Colleague", "voice": "echo", "symbol": "lightbulb", "color": "#6366F1",
                    "opening": "What's a project that turned out completely differently than you expected?",
                    "follow_up": "Ask what changed for them afterwards.",
                    "fallback": "Huh. And did that change how you work now?",
                },
            },
            "remix": {
                "title": "Remix: the trip story",
                "context": "At a family dinner, someone asks about your recent trip.",
                "partner": {
                    "name": "Lena", "role": "Relative at dinner", "voice": "shimmer", "symbol": "airplane",
                    "color": "#FF8A3D",
                    "opening": "So how was the trip? Tell us everything!",
                    "follow_up": "Ask what the best moment was.",
                    "fallback": "And what was the best moment?",
                },
            },
            "real": {
                "prompt": "Tell a story this week with a clear setup, turning point and change.",
                "alt_title": "Tell an AI colleague a story instead.",
                "partner": {
                    "name": "Omar", "role": "Colleague", "voice": "echo", "symbol": "lightbulb", "color": "#6366F1",
                    "opening": "Got any good stories from this month?",
                    "follow_up": "Ask what changed.",
                    "fallback": "So what changed after that?",
                },
                "questions": ["What was the turning point?", "Did your listener react at the turn?",
                              "What changed in the story?"],
            },
        },
        {
            "title": "Make it concrete",
            "dimension": "clarity",
            "target": "Include one specific sensory detail that lets the listener picture the scene.",
            "summary": "One concrete detail does more than ten adjectives.",
            "why": "Specific details make stories believable and vivid. Vague ones ('it was crazy') are forgotten.",
            "example": "\"The kitchen smelled like burnt sugar, and the smoke alarm was chirping like an angry bird.\"",
            "example_explanation": "Smell and sound put the listener right in the room.",
            "seconds": 75,
            "learn": {
                "context": "A friend asks about the best meal you've ever had.",
                "partner": {
                    "name": "Ruby", "role": "Friend", "voice": "coral", "symbol": "fork.knife.circle",
                    "color": "#FF8A3D",
                    "opening": "What's the best meal you've ever had? Paint me a picture.",
                    "follow_up": "Ask what it was like to be there.",
                    "fallback": "Okay, now I'm hungry. What was it like being there?",
                },
            },
            "remix": {
                "title": "Remix: your first week",
                "context": "A new colleague asks what your first week at the company was like.",
                "partner": {
                    "name": "Kai", "role": "New colleague", "voice": "ash", "symbol": "building",
                    "color": "#2F9BFF",
                    "opening": "What was your first week here like?",
                    "follow_up": "Ask about one moment they remember clearly.",
                    "fallback": "Is there a moment from that week you still remember?",
                },
            },
            "real": {
                "prompt": "Tell a story this week with at least one sensory detail: a smell, a sound, a texture.",
                "alt_title": "Describe a memory to an AI friend instead.",
                "partner": {
                    "name": "Ruby", "role": "Friend", "voice": "coral", "symbol": "fork.knife.circle",
                    "color": "#FF8A3D",
                    "opening": "Tell me about your favorite place as a kid.",
                    "follow_up": "Ask what it felt like to be there.",
                    "fallback": "What did it feel like to be there?",
                },
                "questions": ["What detail did you use?", "Could they picture it?", "What was vague that you could sharpen?"],
            },
        },
        {
            "title": "Land the meaning",
            "dimension": "concision",
            "target": "End with one sentence about why the story mattered — then stop.",
            "summary": "Stick the landing instead of trailing off.",
            "why": "Stories that trail off ('…so yeah') lose their impact. One line of meaning gives listeners "
            "something to keep.",
            "example": "\"…and that's when I learned that asking for help early is cheaper than fixing things late.\"",
            "example_explanation": "One clear sentence of meaning, then silence.",
            "seconds": 75,
            "learn": {
                "context": "A mentee asks about a mistake you learned from.",
                "partner": {
                    "name": "Leo", "role": "Mentee", "voice": "verse", "symbol": "graduationcap",
                    "color": "#10B3A3",
                    "opening": "What's a mistake you made early on that taught you something?",
                    "follow_up": "Ask how they'd apply that lesson to their (the mentee's) situation.",
                    "fallback": "How would you apply that if you were in my position?",
                },
            },
            "remix": {
                "title": "Remix: the farewell toast",
                "context": "You're giving a short toast at a colleague's farewell.",
                "partner": {
                    "name": "Dana", "role": "Party host", "voice": "shimmer", "symbol": "wineglass",
                    "color": "#E64980",
                    "opening": "Alright everyone, quiet down — you wanted to say a few words?",
                    "follow_up": "React as a guest who loved it and ask what they'll miss most.",
                    "fallback": "Aw. What will you miss most about working with them?",
                },
            },
            "real": {
                "prompt": "This week, end a story with one sentence about why it mattered — and then stop talking.",
                "alt_title": "Share a lesson with an AI mentee instead.",
                "partner": {
                    "name": "Leo", "role": "Mentee", "voice": "verse", "symbol": "graduationcap",
                    "color": "#10B3A3",
                    "opening": "What's the best advice you ever ignored?",
                    "follow_up": "Ask what they took from it.",
                    "fallback": "So what did you take from it?",
                },
                "questions": ["What was your last sentence?", "Did you stop after it?", "How did they respond?"],
            },
        },
    ],
    "public_speaking": [
        {
            "title": "Open strong",
            "dimension": "structure",
            "target": "Open with a hook — a question, a surprising fact or a short moment — then preview your "
            "three points in one sentence.",
            "summary": "Earn attention in the first fifteen seconds.",
            "why": "Audiences decide in seconds whether to listen. A hook plus a preview tells them why to care and "
            "where you're going.",
            "example": "\"Last year our team spent 400 hours in status meetings. Today: why that happened, what we "
            "changed, and what you can steal.\"",
            "example_explanation": "A surprising number as a hook, then a three-part preview.",
            "seconds": 60,
            "learn": {
                "context": "You're opening a five-minute talk at an all-hands about a project you led.",
                "partner": {
                    "name": "Dana", "role": "Event host", "voice": "shimmer", "symbol": "music.mic",
                    "color": "#E64980",
                    "opening": "Alright everyone, next up. The floor is yours.",
                    "follow_up": "React as an audience member: ask one question about why this matters to your "
                    "team.",
                    "fallback": "Quick question before you go on — why should the sales team care about this?",
                },
            },
            "remix": {
                "title": "Remix: the wedding toast opener",
                "context": "You're opening a toast at a friend's wedding.",
                "partner": {
                    "name": "Sam", "role": "Wedding guest", "voice": "ash", "symbol": "heart.text.square",
                    "color": "#FF8A3D",
                    "opening": "Everyone's glasses are full — go for it!",
                    "follow_up": "React as a guest and ask for the story behind it.",
                    "fallback": "Ha! Wait, what's the story behind that?",
                },
            },
            "real": {
                "prompt": "In your next presentation or meeting kickoff, open with a hook and a one-sentence preview.",
                "alt_title": "Open a talk for an AI audience instead.",
                "partner": {
                    "name": "Dana", "role": "Event host", "voice": "shimmer", "symbol": "music.mic",
                    "color": "#E64980",
                    "opening": "You've got five minutes — whenever you're ready.",
                    "follow_up": "Ask one audience question.",
                    "fallback": "Can you say more about the second point?",
                },
                "questions": ["What was your hook?", "Did you preview your points?", "When did the room start listening?"],
            },
        },
        {
            "title": "Use the power of the pause",
            "dimension": "clarity",
            "target": "Pause for a full beat after each key point.",
            "summary": "Pauses make you sound confident and give ideas time to land.",
            "why": "Nervous speakers rush. Pausing after key points helps the audience absorb them — and tends to "
            "replace filler words.",
            "example": "\"We cut onboarding from two weeks to two days. … Two days. … Here's how.\"",
            "example_explanation": "The pause after the key number makes it land, and the repetition makes it stick.",
            "seconds": 60,
            "learn": {
                "context": "You're presenting one key result to leadership.",
                "partner": {
                    "name": "Grace", "role": "VP in the audience", "voice": "sage", "symbol": "person.crop.square",
                    "color": "#9B5DE5",
                    "opening": "Go ahead — what's the headline result?",
                    "follow_up": "Ask them to repeat the most important number and say what it means for the "
                    "business.",
                    "fallback": "Say that number again — what does it mean for us?",
                },
            },
            "remix": {
                "title": "Remix: news for a nervous team",
                "context": "You're explaining an organizational change to a nervous team.",
                "partner": {
                    "name": "Chris", "role": "Team member", "voice": "echo", "symbol": "person.3",
                    "color": "#10B3A3",
                    "opening": "Okay, we're all here. What's this about?",
                    "follow_up": "Ask one worried question about what changes for them.",
                    "fallback": "So what actually changes for us day to day?",
                },
            },
            "real": {
                "prompt": "In your next presentation or long answer, pause for a full beat after each key point.",
                "alt_title": "Present a result to an AI leader instead.",
                "partner": {
                    "name": "Grace", "role": "VP", "voice": "sage", "symbol": "person.crop.square", "color": "#9B5DE5",
                    "opening": "What's the one thing you want us to remember from this quarter?",
                    "follow_up": "Ask what it means.",
                    "fallback": "And what does that mean for next quarter?",
                },
                "questions": ["Where did you pause?", "Did it feel long to you?", "How did listeners react?"],
            },
        },
        {
            "title": "One idea per sentence",
            "dimension": "concision",
            "target": "Keep sentences short — one idea each, no \"and… and… and\".",
            "summary": "Short sentences are easier to say and easier to follow.",
            "why": "Long, chained sentences force listeners to hold too much in their heads. One idea per sentence "
            "keeps them with you.",
            "example": "\"The app is slow. Users notice. Last month, 12% gave up at checkout. We can fix it in two "
            "sprints.\"",
            "example_explanation": "Four short sentences, four ideas, zero 'and'.",
            "seconds": 60,
            "learn": {
                "context": "Explain a technical problem to non-technical stakeholders.",
                "partner": {
                    "name": "Hannah", "role": "Stakeholder", "voice": "coral", "symbol": "person.crop.circle",
                    "color": "#2F9BFF",
                    "opening": "I keep hearing there's a problem with the system. Can you explain it in plain English?",
                    "follow_up": "Say you lost them at one point and ask them to explain that part again simply.",
                    "fallback": "You lost me in the middle there. Can you say that part again, simply?",
                },
            },
            "remix": {
                "title": "Remix: the neighborhood pitch",
                "context": "Pitch a community project at a neighborhood meeting.",
                "partner": {
                    "name": "Walter", "role": "Neighbor", "voice": "onyx", "symbol": "house.and.flag",
                    "color": "#7CB518",
                    "opening": "We've got ten minutes left. You wanted to propose something?",
                    "follow_up": "Ask one skeptical question about cost or effort.",
                    "fallback": "Sounds nice, but who's going to pay for it?",
                },
            },
            "real": {
                "prompt": "In your next explanation at work or school, keep each sentence to one idea.",
                "alt_title": "Explain a problem to an AI stakeholder instead.",
                "partner": {
                    "name": "Hannah", "role": "Stakeholder", "voice": "coral", "symbol": "person.crop.circle",
                    "color": "#2F9BFF",
                    "opening": "Can you explain what your team actually does?",
                    "follow_up": "Ask them to simplify one part.",
                    "fallback": "Can you say that more simply?",
                },
                "questions": ["Which sentence ran long?", "Did anyone ask you to repeat?", "What would you cut?"],
            },
        },
        {
            "title": "Answer audience questions",
            "dimension": "listening",
            "target": "Paraphrase the question, answer in two sentences, then check if it answered it.",
            "summary": "Handle Q&A with calm, clear answers.",
            "why": "Paraphrasing shows you listened and buys thinking time. Checking back makes sure you actually "
            "answered.",
            "example": "\"So the question is whether this works for small teams. Yes — our smallest pilot team had "
            "four people, and they saw the same gains. Does that answer it?\"",
            "example_explanation": "Paraphrase, a two-sentence answer, then a check.",
            "seconds": 45,
            "learn": {
                "context": "Q&A after your talk. An audience member asks a tough question.",
                "partner": {
                    "name": "Felix", "role": "Audience member", "voice": "echo", "symbol": "hand.raised",
                    "color": "#E64980",
                    "opening": "Thanks for the talk. But isn't this just going to add more process for everyone?",
                    "follow_up": "Say their answer missed your actual concern (it's about your team's time) and ask "
                    "again more specifically.",
                    "fallback": "I don't think that answers it. My team is already stretched — where does the time "
                    "come from?",
                },
            },
            "remix": {
                "title": "Remix: the skeptical town hall",
                "context": "A town-hall Q&A where an employee asks a skeptical question.",
                "partner": {
                    "name": "Maria", "role": "Employee", "voice": "shimmer", "symbol": "person.wave.2",
                    "color": "#FF8A3D",
                    "opening": "Why should we believe this reorganization will be different from the last one?",
                    "follow_up": "Ask a follow-up that tests whether they understood the worry.",
                    "fallback": "Okay, but last time people lost their teams. Will that happen again?",
                },
            },
            "real": {
                "prompt": "Next time you're asked a question in a meeting or class, paraphrase it, answer in two "
                "sentences, then check.",
                "alt_title": "Take audience questions from an AI instead.",
                "partner": {
                    "name": "Felix", "role": "Audience member", "voice": "echo", "symbol": "hand.raised",
                    "color": "#E64980",
                    "opening": "What would you say is the biggest risk with your idea?",
                    "follow_up": "Push back once.",
                    "fallback": "Isn't that a bit optimistic?",
                },
                "questions": ["Did you paraphrase first?", "Was your answer two sentences?", "Did you check back?"],
            },
        },
    ],
}

# The "Job interviews" track (US hiring and Indian campus placements) lives with the market content.
from .content.interviews_track import INTERVIEWS_TRACK as _INTERVIEWS_TRACK  # noqa: E402
from .content.interviews_track import TRACK as _INTERVIEWS_INFO  # noqa: E402

TRACKS[_INTERVIEWS_INFO["id"]] = {k: v for k, v in _INTERVIEWS_INFO.items() if k != "id"}
_CONTENT[_INTERVIEWS_INFO["id"]] = _INTERVIEWS_TRACK

MODULES: dict[str, ModuleDef] = {}
MODULES_BY_TRACK: dict[str, list[ModuleDef]] = {}
MISSIONS: dict[str, MissionDef] = {}
for _track_id, _modules in _CONTENT.items():
    MODULES_BY_TRACK[_track_id] = []
    for _index, _spec in enumerate(_modules, start=1):
        _module_def = _module(_track_id, _index, _spec)
        MODULES[_module_def.id] = _module_def
        MODULES_BY_TRACK[_track_id].append(_module_def)
        for _mission in _module_def.missions:
            MISSIONS[_mission.id] = _mission

# Suggested goal from the onboarding answers (the user can always pick another).
EASE_TO_TRACK = {
    "persuading": "negotiation",
    "concise": "business",
    "contributing": "business",
    "connecting": "conversational",
    "explaining": "public_speaking",
}
CONTEXT_TO_TRACK = {
    "meetings": "business",
    "interviews": "interviews",
    "networking": "conversational",
    "social": "conversational",
}


def suggest_track(contexts_ranked: list[str], ease_targets: list[str]) -> str:
    for ease in ease_targets:
        if ease in EASE_TO_TRACK:
            return EASE_TO_TRACK[ease]
    for context in contexts_ranked:
        if context in CONTEXT_TO_TRACK:
            return CONTEXT_TO_TRACK[context]
    return "business"
