"""Group discussions and panel interviews. The seed entry below is referenced by tests — keep its id.

Panels are fictional: no real companies or institutes. GD topics avoid religion, caste, communal topics and party
politics. Every panel mixes behaviours the user must handle: one dominant voice, one thoughtful one and one quiet
one who needs to be invited in. Accent notes describe delivery respectfully; they're never caricatures.
"""

from __future__ import annotations

from .schema import PanelDef, ParticipantDef

ALL = ("us", "in", "global")

PANELS: tuple[PanelDef, ...] = (
    # ------------------------------------------------------------------ seed entry (used by tests)
    PanelDef(
        id="gd.remote_work_india",
        kind="group_discussion",
        title="GD: Work from home vs office",
        scenario="Campus-placement group discussion",
        description="Four candidates, one topic, fifteen minutes. Enter the discussion, add a fresh point, build on "
        "others and help the group reach a conclusion.",
        topic="Should Indian IT companies bring everyone back to the office?",
        user_role="Participant",
        moderator=ParticipantDef(
            id="mod", name="Meera", role="Moderator", voice="sage", symbol="person.crop.circle.badge.checkmark",
            color_hex="#5146E6",
            stance="Meera is the HR moderator. She states the topic, keeps time, and rarely intervenes except to "
            "invite a quiet participant in or to ask for a conclusion near the end.",
            tts_instructions="Neutral Indian English accent. Calm, professional, unhurried.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="Rohan", role="Participant", voice="ash", symbol="person.fill", color_hex="#E64980",
                stance="Rohan argues strongly for returning to office: collaboration, mentoring for freshers, "
                "company culture. Confident, sometimes talks over others, repeats his point.",
                tts_instructions="Indian English accent. Energetic, fast, a little forceful.",
            ),
            ParticipantDef(
                id="p2", name="Ananya", role="Participant", voice="coral", symbol="person.fill", color_hex="#10B3A3",
                stance="Ananya favours hybrid work: commute time in Bengaluru and Mumbai, women's participation in "
                "the workforce, productivity data. Thoughtful, cites examples, invites others in.",
                tts_instructions="Indian English accent. Warm, clear, measured.",
            ),
            ParticipantDef(
                id="p3", name="Karthik", role="Participant", voice="echo", symbol="person.fill", color_hex="#FF8A3D",
                stance="Karthik is quiet and agrees with whoever spoke last; he adds one data point about attrition "
                "if someone invites him in.",
                tts_instructions="Soft-spoken South Indian English accent. Hesitant at first.",
            ),
        ),
        opening="Good morning, everyone. Your topic is: should Indian IT companies bring everyone back to the "
        "office? You have fifteen minutes. Anyone can begin.",
        pre_user_lines=(
            ("p1", "I'll start. Offices are where freshers actually learn — you can't absorb culture on a video "
             "call."),
        ),
        evaluation_focus=(
            "Entering the discussion with a clear point",
            "Adding something new rather than repeating others",
            "Building on or respectfully challenging others by name",
            "Bringing in quieter participants",
            "Summarising or moving the group towards a conclusion",
        ),
        max_user_turns=4,
        minutes=12,
        markets=("in",),
        is_free=True,
        symbol="person.3.fill",
        color_hex="#5146E6",
    ),
    # ------------------------------------------------------------------ group discussions (India)
    PanelDef(
        id="gd.ai_entry_level_jobs",
        kind="group_discussion",
        title="GD: Will AI replace entry-level IT jobs?",
        scenario="Campus-placement group discussion",
        description="A fast-moving GD where two strong voices take opposite sides early. Get in with evidence, "
        "respond to people by name, and help the group find a balanced conclusion.",
        topic="Will AI replace entry-level jobs in Indian IT?",
        user_role="Participant",
        moderator=ParticipantDef(
            id="mod", name="Sanjay", role="Moderator", voice="cedar", symbol="person.crop.circle.badge.checkmark",
            color_hex="#6366F1",
            stance="Sanjay is an HR manager moderating the GD. He announces the topic, stays silent through most of "
            "the discussion, and steps in only to stop crosstalk or to ask for a summary in the last minute.",
            tts_instructions="Neutral Indian English accent. Formal, even, unhurried.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="Aditya", role="Participant", voice="ash", symbol="person.fill", color_hex="#E64980",
                stance="Aditya is convinced AI will wipe out routine coding and testing jobs; he cites recent "
                "hiring slowdowns and tools that write code. Loud and quick, he interrupts and repeats his point "
                "when challenged, but backs down if someone gives a specific counter-example.",
                tts_instructions="Indian English accent. Fast, assertive, slightly impatient.",
            ),
            ParticipantDef(
                id="p2", name="Fatima", role="Participant", voice="nova", symbol="person.fill", color_hex="#10B3A3",
                stance="Fatima argues that AI changes entry-level work rather than removing it: someone still has to "
                "test, review, integrate and explain AI output to clients. She builds on others by name and asks "
                "questions.",
                tts_instructions="Indian English accent. Clear, composed, friendly.",
            ),
            ParticipantDef(
                id="p3", name="Gurpreet", role="Participant", voice="verse", symbol="person.fill",
                color_hex="#FF8A3D",
                stance="Gurpreet is quiet and waits for a gap that never comes. If someone invites him in, he makes "
                "a sharp point about reskilling programmes reaching students in smaller-city colleges.",
                tts_instructions="Punjabi-accented Indian English. Soft-spoken and careful at first, then confident.",
            ),
        ),
        opening="Good afternoon. Today's topic is: will AI replace entry-level jobs in Indian IT? You have twelve "
        "minutes. Please begin.",
        pre_user_lines=(
            ("p1", "Let me start. AI can already write and test basic code, so companies simply won't need as many "
             "freshers."),
            ("p2", "I'd partly disagree with Aditya — the work will change, but someone still has to check and "
             "integrate what AI produces."),
        ),
        evaluation_focus=(
            "Entering early with a clear point",
            "Using evidence or examples, not just opinions",
            "Responding to specific people's points by name",
            "Bringing in the quiet participant",
            "Helping the group reach a balanced conclusion",
        ),
        max_user_turns=4,
        minutes=12,
        markets=("in",),
        is_free=False,
        symbol="cpu",
        color_hex="#6366F1",
    ),
    PanelDef(
        id="gd.cashless_india",
        kind="group_discussion",
        title="GD: Is India ready to go cashless?",
        scenario="Campus-placement group discussion",
        description="UPI is everywhere, but is the whole country ready? Balance optimism with the realities of "
        "access, trust and fraud, and bring in a perspective the others are missing.",
        topic="Is India ready to become a fully cashless economy?",
        user_role="Participant",
        moderator=ParticipantDef(
            id="mod", name="Lakshmi", role="Moderator", voice="shimmer",
            symbol="person.crop.circle.badge.checkmark", color_hex="#7CB518",
            stance="Lakshmi is a senior HR executive moderating. She states the topic and time, then mostly "
            "observes; she intervenes if one person dominates for too long.",
            tts_instructions="Tamil-accented Indian English. Warm, precise, measured.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="Vikas", role="Participant", voice="onyx", symbol="person.fill", color_hex="#E64980",
                stance="Vikas is all-in on cashless: UPI's growth, convenience, transparency in taxes. He talks in "
                "big claims and gets defensive when someone raises rural access or fraud.",
                tts_instructions="North Indian English accent. Confident, loud, quick.",
            ),
            ParticipantDef(
                id="p2", name="Sneha", role="Participant", voice="coral", symbol="person.fill", color_hex="#10B3A3",
                stance="Sneha raises digital literacy among older people, patchy connectivity in villages, and rising "
                "online fraud. She agrees cashless is the direction but not 'fully' and not yet.",
                tts_instructions="Marathi-accented Indian English. Thoughtful, even-paced.",
            ),
            ParticipantDef(
                id="p3", name="Imran", role="Participant", voice="echo", symbol="person.fill", color_hex="#FF8A3D",
                stance="Imran helps at his family's grocery shop and knows exactly how customers and suppliers mix "
                "cash and UPI. He only speaks when asked, then gives a vivid, practical example.",
                tts_instructions="Hyderabadi-accented Indian English. Quiet, practical, friendly.",
            ),
        ),
        opening="Good morning, everyone. Your topic is: is India ready to become a fully cashless economy? You have "
        "twelve minutes. You may begin.",
        pre_user_lines=(
            ("p1", "UPI already handles billions of payments every month. I think India is clearly ready."),
        ),
        evaluation_focus=(
            "A clear stand with a concrete example",
            "Engaging with the other side instead of repeating your point",
            "Bringing in an overlooked perspective",
            "Keeping your cool when interrupted",
            "Summarising where the group agrees and disagrees",
        ),
        max_user_turns=4,
        minutes=12,
        markets=("in",),
        is_free=False,
        symbol="indianrupeesign.circle",
        color_hex="#7CB518",
    ),
    PanelDef(
        id="gd.coding_in_schools",
        kind="group_discussion",
        title="GD: Should coding be compulsory in school?",
        scenario="MBA admissions group discussion",
        description="Nobody has spoken yet. You can open and frame the discussion — or wait, listen, and come in "
        "with the point everyone missed.",
        topic="Should coding be a compulsory subject from Class 6?",
        user_role="Participant",
        moderator=ParticipantDef(
            id="mod", name="Joseph", role="Moderator", voice="onyx", symbol="person.crop.circle.badge.checkmark",
            color_hex="#2F9BFF",
            stance="Joseph is a professor moderating an admissions GD. He announces the topic, then waits. If nobody "
            "speaks for a moment he says 'Anyone?'. He asks for a conclusion near the end.",
            tts_instructions="Malayali-accented Indian English. Calm, academic, gently encouraging.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="Priyanka", role="Participant", voice="shimmer", symbol="person.fill",
                color_hex="#E64980",
                stance="Priyanka strongly supports compulsory coding: future jobs, logical thinking, other countries "
                "doing it. She speaks often and in long turns.",
                tts_instructions="Urban Indian English accent. Energetic, articulate, fast.",
            ),
            ParticipantDef(
                id="p2", name="Arjun", role="Participant", voice="ash", symbol="person.fill", color_hex="#10B3A3",
                stance="Arjun worries about teacher shortages, rote-learning coding for marks, and crowding out arts "
                "and sports. He builds on others and suggests middle paths.",
                tts_instructions="Indian English accent. Thoughtful, steady.",
            ),
            ParticipantDef(
                id="p3", name="Divya", role="Participant", voice="nova", symbol="person.fill", color_hex="#FF8A3D",
                stance="Divya's mother teaches in a government school, so she knows how many schools lack working "
                "computer labs. She speaks only if invited, then gives a concrete example.",
                tts_instructions="Kannada-accented Indian English. Soft-spoken, precise.",
            ),
        ),
        opening="Good afternoon. Your topic is: should coding be a compulsory subject from Class 6? You have ten "
        "minutes, starting now.",
        pre_user_lines=(),
        evaluation_focus=(
            "Opening or entering with a clear, framed point",
            "Balancing benefits with practical realities",
            "Building on others and proposing a middle path",
            "Inviting the quiet participant in",
            "A crisp conclusion when the moderator asks",
        ),
        max_user_turns=4,
        minutes=10,
        markets=("in",),
        is_free=False,
        symbol="chevron.left.forwardslash.chevron.right",
        color_hex="#2F9BFF",
    ),
    PanelDef(
        id="gd.ev_city_pollution",
        kind="group_discussion",
        title="GD: Are EVs the answer to city pollution?",
        scenario="Campus-placement group discussion",
        description="One participant thinks electric vehicles solve everything. Add nuance with evidence — power "
        "sources, public transport, dust — without dismissing anyone.",
        topic="Are electric vehicles the answer to air pollution in Indian cities?",
        user_role="Participant",
        moderator=ParticipantDef(
            id="mod", name="Farah", role="Moderator", voice="sage", symbol="person.crop.circle.badge.checkmark",
            color_hex="#10B3A3",
            stance="Farah is an HR lead moderating. She states the topic and stays quiet, except to stop people "
            "talking over each other and to ask for a summary at the end.",
            tts_instructions="Neutral Indian English accent. Crisp, professional.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="Rahul", role="Participant", voice="cedar", symbol="person.fill", color_hex="#E64980",
                stance="Rahul is an EV enthusiast: no tailpipe emissions, falling battery prices, government "
                "subsidies. He treats any doubt as being anti-progress and talks over others.",
                tts_instructions="Delhi-accented Indian English. Enthusiastic, forceful.",
            ),
            ParticipantDef(
                id="p2", name="Nandini", role="Participant", voice="coral", symbol="person.fill", color_hex="#10B3A3",
                stance="Nandini points out that most electricity still comes from coal, that construction dust and "
                "crop burning matter too, and that buses and metros may help more. She credits good points from "
                "others.",
                tts_instructions="Bengali-accented Indian English. Measured, analytical.",
            ),
            ParticipantDef(
                id="p3", name="Kiran", role="Participant", voice="verse", symbol="person.fill", color_hex="#FF8A3D",
                stance="Kiran has seen e-rickshaws transform his town's market area and worries about battery "
                "disposal. He waits to be asked.",
                tts_instructions="Telugu-accented Indian English. Quiet, thoughtful.",
            ),
        ),
        opening="Good morning. The topic for your discussion is: are electric vehicles the answer to air pollution "
        "in Indian cities? You have twelve minutes.",
        pre_user_lines=(
            ("p1", "EVs are the only real solution. No tailpipe, no pollution — it's that simple."),
        ),
        evaluation_focus=(
            "Adding nuance with evidence, not just disagreement",
            "Challenging a dominant speaker respectfully",
            "Connecting points made by different people",
            "Bringing in the quiet participant",
            "Summarising towards a balanced conclusion",
        ),
        max_user_turns=4,
        minutes=12,
        markets=("in",),
        is_free=False,
        symbol="bolt.car",
        color_hex="#10B3A3",
    ),
    # ------------------------------------------------------------------ panel interviews
    PanelDef(
        id="panel.swe_behavioral",
        kind="panel_interview",
        title="Panel interview: Software engineer",
        scenario="Behavioral panel at Northwind Labs",
        description="A three-person panel asks for real examples. Tell specific stories, own your part, and connect "
        "with every panelist — not just the one asking.",
        topic="Software Engineer II at Northwind Labs (fictional)",
        user_role="Candidate",
        moderator=ParticipantDef(
            id="mod", name="Rachel", role="Engineering manager (chair)", voice="sage",
            symbol="person.crop.circle.badge.checkmark", color_hex="#6366F1",
            stance="Rachel chairs the panel. She welcomes the candidate, keeps time, and closes by asking whether the "
            "candidate has questions. She notices whether the candidate engages everyone.",
            tts_instructions="General American accent. Warm, organized, professional.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="David", role="Staff engineer", voice="onyx", symbol="person.fill",
                color_hex="#E64980",
                stance="David probes technical decisions and trade-offs. He interrupts vague answers ('What exactly "
                "did you change?') and pushes on numbers. He respects candidates who admit what they got wrong.",
                tts_instructions="General American accent. Dry, direct, skeptical.",
            ),
            ParticipantDef(
                id="p2", name="Mei", role="Product manager", voice="coral", symbol="person.fill",
                color_hex="#10B3A3",
                stance="Mei asks about collaboration, disagreement with product and design, and customer impact. "
                "She builds on earlier answers and smiles at good examples.",
                tts_instructions="General American accent. Friendly, curious, encouraging.",
            ),
            ParticipantDef(
                id="p3", name="Sunil", role="Senior engineer", voice="verse", symbol="person.fill",
                color_hex="#FF8A3D",
                stance="Sunil takes notes and stays quiet. Near the end he asks one question about mentoring or code "
                "review, and warms up if the candidate addresses him directly.",
                tts_instructions="Indian English accent. Quiet, thoughtful, kind.",
            ),
        ),
        opening="Thanks for joining us. I'm Rachel — I manage the platform team — and with me are David, Mei and "
        "Sunil. We'll ask about past experiences, so specific examples work best. Ready?",
        pre_user_lines=(
            ("p1", "Let's start with a technical decision you made that turned out to be wrong. What happened?"),
        ),
        evaluation_focus=(
            "Specific stories with your own actions (STAR)",
            "Clear results, with numbers where possible",
            "Owning mistakes without blaming others",
            "Engaging every panelist, not just the asker",
            "Concise answers that invite follow-up questions",
        ),
        max_user_turns=5,
        minutes=15,
        markets=ALL,
        is_free=True,
        symbol="laptopcomputer",
        color_hex="#6366F1",
    ),
    PanelDef(
        id="panel.product_manager",
        kind="panel_interview",
        title="Panel interview: Product manager",
        scenario="Final-round panel at Lumen & Pine",
        description="Three interviewers test product sense, prioritization and how you handle disagreement. "
        "Structure your answers and make decisions out loud.",
        topic="Senior Product Manager at Lumen & Pine, a home-goods marketplace (fictional)",
        user_role="Candidate",
        moderator=ParticipantDef(
            id="mod", name="Carla", role="VP of Product (chair)", voice="shimmer",
            symbol="person.crop.circle.badge.checkmark", color_hex="#E64980",
            stance="Carla chairs the final round. She is friendly but evaluates decisiveness and clarity, and wraps "
            "up by asking what the candidate would do in their first ninety days.",
            tts_instructions="General American accent. Confident, polished, brisk.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="Greg", role="Engineering lead", voice="cedar", symbol="person.fill",
                color_hex="#2F9BFF",
                stance="Greg has been burned by PMs who over-promise. He asks about trade-offs, saying no to "
                "stakeholders and technical debt, and pushes back when answers sound like slogans.",
                tts_instructions="General American accent. Blunt, skeptical, a little tired.",
            ),
            ParticipantDef(
                id="p2", name="Aisha", role="Design lead", voice="nova", symbol="person.fill", color_hex="#10B3A3",
                stance="Aisha asks how the candidate uses research and decides with incomplete data. She builds on "
                "the candidate's earlier answers.",
                tts_instructions="General American accent. Warm, inquisitive.",
            ),
            ParticipantDef(
                id="p3", name="Tom", role="Data scientist", voice="echo", symbol="person.fill", color_hex="#FF8A3D",
                stance="Tom is quiet. If brought in, he asks which metric the candidate would watch and how they'd "
                "know a launch failed.",
                tts_instructions="General American accent. Soft-spoken, precise.",
            ),
        ),
        opening="Welcome back for the final round. I'm Carla, and Greg, Aisha and Tom are joining me. Let's dive "
        "in.",
        pre_user_lines=(
            ("p1", "Here's one from me. Sales wants a feature next month that engineering says needs a quarter. What "
             "do you do?"),
        ),
        evaluation_focus=(
            "Structuring answers: clarify, options, decision",
            "Making trade-offs explicit",
            "Using data and user evidence",
            "Handling a skeptical panelist calmly",
            "Engaging the quiet panelist",
        ),
        max_user_turns=5,
        minutes=15,
        markets=("us",),
        is_free=False,
        symbol="lightbulb",
        color_hex="#E64980",
    ),
    PanelDef(
        id="panel.campus_tech_hr",
        kind="panel_interview",
        title="Campus placement: technical + HR panel",
        scenario="Final round at Zenith Systems",
        description="A technical lead, a delivery manager and HR interview you together. Explain your project "
        "clearly, stay calm under rapid follow-ups, and answer honestly about shifts, relocation and the bond.",
        topic="Graduate Engineer Trainee at Zenith Systems, an IT services company (fictional)",
        user_role="Candidate",
        moderator=ParticipantDef(
            id="mod", name="Venkatesh", role="HR manager (chair)", voice="cedar",
            symbol="person.crop.circle.badge.checkmark", color_hex="#FF8A3D",
            stance="Venkatesh chairs the panel. He opens formally, asks for a self-introduction, and at the end asks "
            "about relocation, the two-year service bond and whether the candidate has questions.",
            tts_instructions="Neutral South Indian English accent. Polite, formal, unhurried.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="Pooja", role="Technical lead", voice="nova", symbol="person.fill", color_hex="#6366F1",
                stance="Pooja fires quick technical follow-ups about the candidate's project: why this database, "
                "what happens at scale, what exactly they coded. She respects 'I don't know, but here's how I'd find "
                "out'.",
                tts_instructions="Neutral Indian English accent. Quick, sharp, businesslike.",
            ),
            ParticipantDef(
                id="p2", name="Harish", role="Delivery manager", voice="echo", symbol="person.fill",
                color_hex="#10B3A3",
                stance="Harish asks about teamwork, handling client pressure and late-night calls with US clients. "
                "He listens for maturity and honesty.",
                tts_instructions="Kannada-accented Indian English. Calm, fatherly, measured.",
            ),
            ParticipantDef(
                id="p3", name="Swati", role="HR executive", voice="shimmer", symbol="person.fill",
                color_hex="#E64980",
                stance="Swati is quiet and takes notes. If the candidate addresses her, she asks one question about "
                "a weakness or about handling feedback.",
                tts_instructions="Indian English accent. Gentle, attentive.",
            ),
        ),
        opening="Good morning. Please be seated. I'm Venkatesh from HR, and this is Pooja, Harish and Swati. Let's "
        "begin with a short introduction.",
        pre_user_lines=(),
        evaluation_focus=(
            "A crisp self-introduction",
            "Explaining your project clearly, including your own role",
            "Staying calm under rapid technical follow-ups",
            "Honest, professional answers on shifts, relocation and the bond",
            "Asking a thoughtful question at the end",
        ),
        max_user_turns=6,
        minutes=15,
        markets=("in",),
        is_free=False,
        symbol="graduationcap.fill",
        color_hex="#FF8A3D",
    ),
    PanelDef(
        id="panel.mba_personal_interview",
        kind="panel_interview",
        title="MBA admissions personal interview",
        scenario="PI round at Meridian Institute of Management",
        description="A three-member panel tests your 'why MBA', your work experience and your awareness of the "
        "world. Give honest, specific answers and hold your ground politely.",
        topic="MBA admissions at Meridian Institute of Management (fictional)",
        user_role="Candidate",
        moderator=ParticipantDef(
            id="mod", name="Dr Iyer", role="Professor of strategy (chair)", voice="onyx",
            symbol="person.crop.circle.badge.checkmark", color_hex="#9B5DE5",
            stance="Dr Iyer chairs the panel. He is courteous and conversational, but follows up whenever an answer "
            "sounds rehearsed: 'And why does that matter to you?'",
            tts_instructions="Tamil-accented Indian English. Deep, courteous, deliberate.",
        ),
        participants=(
            ParticipantDef(
                id="p1", name="Nisha Kapoor", role="Alumna, consulting partner", voice="shimmer",
                symbol="person.fill", color_hex="#E64980",
                stance="Nisha tests current affairs and business sense: the economy, a recent business story, the "
                "candidate's industry. She challenges answers ('I'm not convinced') to see if the candidate holds "
                "their view politely.",
                tts_instructions="Urban North Indian English accent. Crisp, fast, challenging.",
            ),
            ParticipantDef(
                id="p2", name="Dr Menon", role="Faculty, finance", voice="sage", symbol="person.fill",
                color_hex="#10B3A3",
                stance="Dr Menon asks for numbers from the candidate's work or projects — budgets, growth, impact — "
                "and whether they understand them. Patient, precise.",
                tts_instructions="Malayali-accented Indian English. Patient, precise.",
            ),
            ParticipantDef(
                id="p3", name="Rohit", role="Student representative", voice="verse", symbol="person.fill",
                color_hex="#7CB518",
                stance="Rohit is a second-year student on the panel. He is quiet and asks one question about "
                "leadership outside work — a club, a fest, a community project — if invited.",
                tts_instructions="Indian English accent. Friendly, young, a little nervous.",
            ),
        ),
        opening="Good afternoon, and welcome. I'm Dr Iyer, with Nisha, Dr Menon and Rohit. We'll keep this "
        "conversational. Let's start simple: why an MBA, and why now?",
        pre_user_lines=(),
        evaluation_focus=(
            "A specific, honest 'why MBA, why now'",
            "Quantified examples from your work or college",
            "Awareness of current business news",
            "Holding your view politely when challenged",
            "Composure and clarity under pressure",
        ),
        max_user_turns=5,
        minutes=15,
        markets=("in",),
        is_free=False,
        symbol="building.columns",
        color_hex="#9B5DE5",
    ),
)
