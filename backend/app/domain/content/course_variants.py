"""Market variants for course content. Keys are module ids (override module fields: example,
example_explanation, why, summary) or mission ids (override title, context, real_life_prompt,
ai_alternative_title, and any partner field under "partner").

Only differences go here; anything not overridden uses the base content. The seed entries are used by tests.

India variants swap in Indian names, places, rupees and lakhs, and Indian workplace realities (11-month rental
agreements, notice periods, appraisal cycles, late calls with US clients). Whenever a partner's name changes, the
variant also gives their `character`, so the base name never leaks into prompts. Partners who keep their name but
should sound local get `tts_instructions` only.
"""

from __future__ import annotations

from typing import Any

# Delivery note for partners who are Indian in the India market.
_IN_VOICE = "Indian English accent. Natural and conversational; realistic for the role, never an announcer."


def _in(name: str, character: str, **fields: str) -> dict[str, str]:
    """An Indian partner: new name, matching character, local delivery, plus any other field overrides."""
    return {"name": name, "character": character, "tts_instructions": _IN_VOICE, **fields}


COURSE_VARIANTS: dict[str, dict[str, dict[str, Any]]] = {
    "in": {
        # ------------------------------------------------------------------ business
        "business.m1": {
            "example": "\"I'd go with the Pune vendor. They're 20% cheaper, and they've already cleared our "
            "security audit. What would you want covered before we sign?\"",
        },
        "business.m1.learn": {
            "partner": _in("Arjun", "Arjun, a thoughtful teammate who leans toward the familiar vendor."),
        },
        "business.m1.remix": {
            "partner": _in("Kavya", "Kavya, your manager, who wants a straight answer in the corridor."),
        },
        "business.m1.real": {
            "partner": _in("Sunita", "Sunita, your skip-level manager, who has five minutes and wants a clear "
                           "recommendation."),
        },
        "business.m2.learn": {
            "partner": _in("Shalini", "Shalini, a director who wants the quick version and a date she can repeat "
                           "to her boss."),
        },
        "business.m2.remix": {
            "context": "A worried US client calls during your evening to ask whether their delivery is still on "
            "track.",
            "partner": {
                "role": "US client",
                "character": "Tom, a client in Chicago who has already promised his own boss a launch date.",
                "tts_instructions": "General American accent. Worried, polite, a little tense.",
            },
        },
        "business.m2.real": {
            "partner": _in("Shalini", "Shalini, a director who wants to know exactly what you need from her."),
        },
        "business.m3": {
            "example": "\"That's a fair worry about cost. The pilot is six lakh, and it replaces a twenty-five lakh "
            "contract if it works. So I'm asking for a yes on the pilot only.\"",
        },
        "business.m3.learn": {
            "context": "You're asking a budget holder for twelve lakh rupees to run a pilot. They're not convinced.",
            "partner": _in(
                "Lata", "Lata, the finance head who controls this year's budget and has seen many pilots fail.",
                opening="I've read your proposal. Honestly, I don't see why we'd spend twelve lakh on this right now.",
            ),
        },
        "business.m3.remix": {
            "partner": {"tts_instructions": _IN_VOICE},
        },
        "business.m3.real": {
            "partner": _in("Lata", "Lata, the finance head, who isn't convinced the team needs another hire."),
        },
        "business.m4": {
            "example": "\"Divya, you've seen the support tickets — what are customers actually complaining about? … "
            "So it's the export step. Then I think we fix that before adding features.\"",
        },
        "business.m4.learn": {
            "partner": _in("Divya", "Divya, an analyst who rarely speaks up but has seen the customer data."),
        },
        "business.m4.remix": {
            "partner": _in("Nikhil", "Nikhil, a direct report who has gone quiet in team meetings lately."),
        },
        "business.m4.real": {
            "partner": _in("Divya", "Divya, a quiet colleague with one idea she hasn't shared yet."),
        },
        # ------------------------------------------------------------------ negotiation
        "negotiation.m1": {
            "example": "\"I'm looking for eighteen lakh fixed. That's in line with market data for this role in "
            "Bengaluru, and I'm bringing the payments experience you said you need.\"",
        },
        "negotiation.m1.learn": {
            "partner": _in(
                "Arvind", "Arvind, a hiring manager at a product company in Bengaluru with a fixed budget band.",
                opening="Before we go further, what CTC are you expecting?",
            ),
        },
        "negotiation.m1.remix": {
            "context": "A prospective client asks what you'd charge to redesign their website.",
            "partner": _in("Ananya", "Ananya, the founder of a skincare brand in Mumbai who loved your portfolio but "
                           "watches every rupee."),
        },
        "negotiation.m1.real": {
            "partner": _in("Ananya", "Ananya, a founder who wants a clear day rate before she commits."),
        },
        "negotiation.m2": {
            "example": "\"What's driving the increase on your side? … So the society maintenance went up and the "
            "building needs waterproofing before the monsoon — it's mostly about covering costs this year. Is that "
            "right?\"",
        },
        "negotiation.m2.learn": {
            "context": "Your landlord announces a rent increase as your 11-month rental agreement comes up for "
            "renewal.",
            "partner": {
                "name": "Mrs Kulkarni",
                "character": "Mrs Kulkarni owns two flats in Pune. Society maintenance and repair costs went up, and "
                "she hates finding new tenants and paying brokerage.",
                "opening": "I wanted to tell you, the rent is going up ten percent when the agreement renews next "
                "month.",
                "follow_up": "If they asked about your reasons, explain them (higher society maintenance, "
                "waterproofing before the monsoon) and mention you'd hate to find a new tenant. If they didn't ask, "
                "stay firm and vague.",
                "fallback": "Society maintenance has gone up, and the building needs waterproofing before the "
                "monsoon. I can't absorb all of that.",
                "tts_instructions": "Marathi-accented Indian English, sixties. Polite but firm, matter-of-fact.",
            },
        },
        "negotiation.m2.remix": {
            "partner": _in(
                "Suresh", "Suresh, an account manager at a software vendor whose compliance costs rose this year.",
                opening="Our renewal pricing is going up eighteen percent this year. I hope that works for you.",
            ),
        },
        "negotiation.m2.real": {
            "partner": {
                "name": "Mrs Kulkarni",
                "character": "Mrs Kulkarni, a landlord in Pune who explains her costs only if asked.",
                "opening": "The rent is going up from next month. I've sent you the new agreement.",
                "fallback": "My costs have gone up across the board this year.",
                "tts_instructions": "Marathi-accented Indian English, sixties. Polite but firm, matter-of-fact.",
            },
        },
        "negotiation.m3.learn": {
            "partner": _in("Varun", "Varun, a friendly colleague who is trying to hand off the partner newsletter."),
        },
        "negotiation.m3.remix": {
            "partner": _in(
                "Pooja", "Pooja, a close friend from college who is short of money this month.",
                opening="This is awkward, but could you lend me twenty thousand till next month?",
            ),
        },
        "negotiation.m3.real": {
            "partner": _in("Varun", "Varun, a colleague who wants you to cover his weekend on-call shift."),
        },
        "negotiation.m4": {
            "example": "\"So we're agreed: eighteen lakh fixed, joining on the 3rd, with a review after six months. "
            "I really appreciated you going back to HR for me. I'll sign the offer letter tonight.\"",
        },
        "negotiation.m4.learn": {
            "partner": _in(
                "Arvind", "Arvind, a hiring manager who has just agreed your terms and wants to close.",
                opening="Okay, I think we can do eighteen lakh fixed with a March joining date. Are we good?",
            ),
        },
        "negotiation.m4.remix": {
            "partner": {
                "name": "Mrs Kulkarni",
                "character": "Mrs Kulkarni, a landlord in Pune who has agreed to a smaller increase.",
                "opening": "Fine. Five percent, and you agree to a one-year lock-in. Deal?",
                "fallback": "Good. When can you sign the new agreement?",
                "tts_instructions": "Marathi-accented Indian English, sixties. Polite but firm, matter-of-fact.",
            },
        },
        "negotiation.m4.real": {
            "partner": _in(
                "Arvind", "Arvind, a hiring manager ready to send the offer letter.",
                opening="Alright, we can meet your number. Anything else before I send the offer letter?",
                follow_up="Ask when they can join, given their notice period.",
                fallback="Great. When could you join, given your notice period?",
            ),
        },
        # ------------------------------------------------------------------ conversational
        "conversational.m1": {
            "example": "\"You said you just got back from Goa — what surprised you most about it?\"",
        },
        "conversational.m1.learn": {
            "context": "You meet someone new at a friend's birthday party.",
            "partner": _in(
                "Aditya", "Aditya, who knows the birthday girl from his badminton group and just got back from a "
                "trip.",
                opening="Hi! I'm Aditya, I know the birthday girl from my badminton group. I just got back from a "
                "trip, so I'm still a bit tired.",
                follow_up="Answer their question with one or two specific details, including something they could "
                "follow up on (you tried scuba diving for the first time and panicked).",
                fallback="Yeah, a week in Goa. I tried scuba diving for the first time and completely panicked.",
            ),
        },
        "conversational.m1.remix": {
            "context": "Small talk over chai in the office pantry, with a colleague you don't know well.",
            "partner": _in(
                "Sneha", "Sneha, a colleague from the finance team whose floor is being renovated.",
                opening="Morning! Long week already — they're renovating our floor, so we're all squeezed in here.",
                fallback="Best part, we finally get a proper pantry. Worst part, I lost my window seat in the move.",
            ),
        },
        "conversational.m1.real": {
            "partner": _in(
                "Aditya", "Aditya, someone new at a party who just started learning the guitar.",
                opening="Hey, I don't think we've met. I'm Aditya — I just started learning the guitar, which is "
                "going terribly.",
                fallback="My neighbours have started playing loud music whenever I practise. I think it's a message.",
            ),
        },
        "conversational.m2": {
            "example": "\"I've been learning to make biryani — badly, but my rice is improving. Do you cook much?\"",
        },
        "conversational.m2.learn": {
            "context": "On a first coffee with someone you matched with, they ask about you.",
            "partner": _in(
                "Riya", "Riya, 27, a UX researcher who loves trekking and old Hindi film songs; a little nervous.",
                fallback="Ha, I love that. I've been trying to learn the guitar, but my neighbours probably hate me.",
            ),
        },
        "conversational.m2.remix": {
            "partner": _in(
                "Aman", "Aman, who joined the team last week and is still finding his feet.",
                fallback="Oh nice! I'm mostly trekking on weekends — trying to climb every fort in the Sahyadris.",
            ),
        },
        "conversational.m2.real": {
            "partner": _in(
                "Riya", "Riya, a friend on a first coffee who loves hearing about people's weeks.",
                fallback="That sounds great. Mine was finally finishing a jigsaw puzzle I've been doing for a month.",
            ),
        },
        "conversational.m3": {
            "example": "\"Mostly work, but the highlight was fixing up my old scooter — I rode to Nandi Hills on "
            "Sunday and got caught in the rain.\"",
        },
        "conversational.m3.learn": {
            "partner": _in("Kunal", "Kunal, a school friend you haven't seen in months."),
        },
        "conversational.m3.remix": {
            "context": "At a tech meetup, someone asks what you do.",
            "partner": _in("Meghna", "Meghna, a product manager at a tech meetup in Bengaluru."),
        },
        "conversational.m3.real": {
            "partner": _in("Kunal", "Kunal, an old school friend catching up after months."),
        },
        "conversational.m4.learn": {
            "partner": _in("Tanya", "Tanya, a friend who loves a good story at dinner."),
        },
        "conversational.m4.remix": {
            "partner": _in("Rahul", "Rahul, a colleague asking about your weekend on Monday morning."),
        },
        "conversational.m4.real": {
            "partner": _in("Tanya", "Tanya, a friend who wants to hear something that surprised you."),
        },
        # ------------------------------------------------------------------ storytelling
        "storytelling.m1.learn": {
            "partner": _in("Sana", "Sana, a friend curious how you ended up in your job."),
        },
        "storytelling.m1.remix": {
            "partner": {"tts_instructions": _IN_VOICE},
        },
        "storytelling.m1.real": {
            "partner": _in("Sana", "Sana, a friend who wants to hear a moment you'll never forget."),
        },
        "storytelling.m2.learn": {
            "partner": {"tts_instructions": _IN_VOICE},
        },
        "storytelling.m2.remix": {
            "context": "At a family dinner, your aunt asks about your recent trip.",
            "partner": {
                "name": "Meena Aunty",
                "role": "Your aunt",
                "character": "Meena Aunty, who wants every detail of your trip, and the photos too.",
                "opening": "Arre, so how was the trip? Tell us everything!",
                "tts_instructions": "Indian English with a warm Hindi lilt, fifties. Excited and affectionate.",
            },
        },
        "storytelling.m2.real": {
            "partner": {"tts_instructions": _IN_VOICE},
        },
        "storytelling.m3.learn": {
            "partner": _in("Ishita", "Ishita, a food-loving friend who wants every detail."),
        },
        "storytelling.m3.remix": {
            "partner": _in("Farhan", "Farhan, a new colleague curious about what the company is really like."),
        },
        "storytelling.m3.real": {
            "partner": _in("Ishita", "Ishita, a friend who wants to hear about your favourite place as a kid."),
        },
        "storytelling.m4.learn": {
            "partner": _in("Kabir", "Kabir, a young engineer you mentor."),
        },
        "storytelling.m4.remix": {
            "context": "You're saying a few words at a colleague's farewell party.",
            "partner": _in(
                "Anjali", "Anjali, who organised the farewell and hands you the mic.",
                role="Farewell organiser",
                opening="Okay everyone, quiet please — you wanted to say a few words?",
            ),
        },
        "storytelling.m4.real": {
            "partner": _in("Kabir", "Kabir, a mentee who wants to know the best advice you ever ignored."),
        },
        # ------------------------------------------------------------------ public speaking
        "public_speaking.m1.learn": {
            "context": "You're opening a five-minute talk at a town hall about a project you led.",
            "partner": _in("Anjali", "Anjali, who is hosting the town hall.", role="Town hall host"),
        },
        "public_speaking.m1.remix": {
            "title": "Remix: the sangeet speech",
            "context": "You're opening a short speech at your cousin's sangeet.",
            "partner": _in(
                "Ritika", "Ritika, the bride's friend, cheering everyone on.",
                role="Sangeet guest",
                opening="Everyone's settled — the mic is yours!",
            ),
        },
        "public_speaking.m1.real": {
            "partner": _in("Anjali", "Anjali, hosting a session where you have five minutes.", role="Event host"),
        },
        "public_speaking.m2.learn": {
            "partner": _in("Sunita", "Sunita, a VP in the audience who wants the headline result first."),
        },
        "public_speaking.m2.remix": {
            "partner": _in("Nikhil", "Nikhil, a team member worried about what the change means for him."),
        },
        "public_speaking.m2.real": {
            "partner": _in("Sunita", "Sunita, a VP who wants the one thing to remember from this quarter."),
        },
        "public_speaking.m3.learn": {
            "partner": _in("Rekha", "Rekha, a business stakeholder who wants it in plain English."),
        },
        "public_speaking.m3.remix": {
            "title": "Remix: the society meeting pitch",
            "context": "Pitch a community project at your housing society's annual general meeting.",
            "partner": {
                "name": "Mr Joshi",
                "role": "Society secretary",
                "character": "Mr Joshi, the society secretary, who worries about anything that might raise the "
                "maintenance charges.",
                "opening": "We have ten minutes left in the AGM. You wanted to propose something?",
                "follow_up": "Ask one skeptical question about the cost or the maintenance charges.",
                "fallback": "Sounds nice, but will this increase our maintenance charges?",
                "tts_instructions": "Marathi-accented Indian English, sixties. Polite, careful about money.",
            },
        },
        "public_speaking.m3.real": {
            "partner": _in("Rekha", "Rekha, a stakeholder who wants to know what your team actually does."),
        },
        "public_speaking.m4.learn": {
            "partner": _in("Siddharth", "Siddharth, a skeptical engineer in the audience."),
        },
        "public_speaking.m4.remix": {
            "partner": _in("Fatima", "Fatima, an employee who lived through the last reorganisation."),
        },
        "public_speaking.m4.real": {
            "partner": _in("Siddharth", "Siddharth, an audience member who likes to test ideas."),
        },
        # ------------------------------------------------------------------ interviews (campus placements)
        "interviews.m1.learn": {
            "context": "A campus-placement interview at an IT services company. The HR panel opens with the classic "
            "question.",
            "partner": {
                "name": "Ritu", "role": "HR, campus hiring", "voice": "coral",
                "character": "Ritu, an HR lead who has interviewed 60 freshers today and can spot a memorised "
                "introduction instantly.",
                "opening": "Good afternoon. Please have a seat. So — tell me about yourself.",
                "tts_instructions": "Neutral Indian English accent. Polite, brisk, professional.",
            },
        },
        "interviews.m1.remix": {
            "context": "At a tech meetup in Hyderabad, an engineer from the company you've applied to asks about you.",
            "partner": _in(
                "Karthik", "Karthik, a senior engineer from the company, chatting at a meetup.",
                opening="Oh, you've applied to us? Nice. So what's your story — what are you into?",
            ),
        },
        "interviews.m1.real": {
            "real_life_prompt": "Say your two-minute introduction to a senior from your college, your placement "
            "coordinator or a friend this week. Keep the three parts: now, proof, why this role.",
            "partner": {
                "opening": "Hi! I'm screening candidates for a few roles this week. Give me the quick version of you.",
                "tts_instructions": _IN_VOICE,
            },
        },
        "interviews.m2": {
            "example": "\"In third year, our fest's registration site crashed the night before launch. As the "
            "backend volunteer, I traced it to one slow query, rewrote it and load-tested it with friends till 3 AM. "
            "The site went live on time and took three thousand registrations on day one.\"",
        },
        "interviews.m2.learn": {
            "context": "A technical interview at an IT services company. The interviewer asks about the hardest "
            "problem you've solved.",
            "partner": _in(
                "Deepak", "Deepak, a project manager who listens for what the candidate personally did.",
                role="Technical interviewer",
            ),
        },
        "interviews.m2.remix": {
            "partner": _in("Shruti", "Shruti, a senior engineer who asks about failures to see how candidates take "
                           "ownership."),
        },
        "interviews.m2.real": {
            "real_life_prompt": "Write down three STAR stories from your projects, internship or college activities — "
            "a win, a conflict and a failure — and tell one out loud to a friend or senior this week.",
            "partner": _in("Deepak", "Deepak, an interviewer who wants results in numbers.",
                           role="Technical interviewer"),
        },
        "interviews.m3": {
            "example": "\"You need freshers who learn fast and can talk to clients. In my internship I picked up "
            "React in two weeks to ship a dashboard the client demoed, and as fest coordinator I handled forty "
            "sponsors on calls. I'd bring both here from day one.\"",
        },
        "interviews.m3.learn": {
            "partner": _in(
                "Anita", "Anita, an HR manager choosing between three strong candidates from your campus.",
                role="HR manager",
                opening="We have met some strong candidates today. Why should we hire you?",
                fallback="You haven't done an internship at a big company, though. Why shouldn't that worry us?",
            ),
        },
        "interviews.m3.remix": {
            "partner": _in("Rohit", "Rohit, a recruiter at a hiring consultancy who screens candidates by phone."),
        },
        "interviews.m3.real": {
            "real_life_prompt": "Pick a real job description from your placement portal. Write down its top two needs "
            "and your proof for each, then say your \"why hire me\" answer out loud until it takes under a minute.",
            "partner": _in("Anita", "Anita, an HR manager who wants one clear reason to choose you.",
                           role="HR manager"),
        },
        "interviews.m4": {
            "example": "\"Earlier you mentioned that freshers here rotate across two client projects in the first "
            "year. How do you decide which project new joiners start on?\"",
        },
        "interviews.m4.learn": {
            "context": "The interview is wrapping up. Earlier, the manager mentioned that the team is moving a "
            "client's banking app to the cloud.",
            "partner": _in(
                "Rashmi", "Rashmi, an engineering manager who mentioned earlier that her team is moving a client's "
                "banking app to the cloud and struggling with release quality.",
                follow_up="Answer their question in two sentences, including one detail they could follow up on "
                "(for example, that the migration slipped twice this year), and see whether they build on it.",
                fallback="Good question. Honestly, the migration has slipped twice this year, so quality is a big "
                "focus.",
            ),
        },
        "interviews.m4.remix": {
            "partner": _in("Mr Thomas", "Mr Thomas, the HR head chairing the final panel, who values candidates who "
                           "listen."),
        },
        "interviews.m4.real": {
            "real_life_prompt": "In your next interview, or a call with a senior, note one thing they say early on and "
            "ask a question about it at the end.",
            "partner": _in(
                "Rashmi", "Rashmi, an engineering manager whose team is hiring twenty freshers this year.",
                opening="We're almost out of time. Any questions for me?",
                fallback="We're hiring twenty freshers this year, so mentoring will matter a lot.",
            ),
        },
    },
}
