"""The "Job interviews" goal track (US hiring and Indian campus placements). Same dict format as the modules in
../course.py `_CONTENT`; India-specific scenario variants live in course_variants.py.

The seed module below is referenced by tests — keep its title and dimension.
"""

from __future__ import annotations

from typing import Any

TRACK = {
    "id": "interviews",
    "title": "Job interviews",
    "subtitle": "Walk in prepared: introductions, stories and strong answers.",
    "symbol": "person.crop.rectangle.stack",
}

INTERVIEWS_TRACK: list[dict[str, Any]] = [
    {
        "title": "Tell me about yourself",
        "dimension": "structure",
        "target": "Answer in three parts: who you are now, one proof point, and why this role.",
        "summary": "A two-minute introduction that sets up the rest of the interview.",
        "why": "It's usually the first question, and interviewers often decide in the first minute whether you can "
        "explain yourself clearly.",
        "example": "\"I'm a final-year computer science student who likes making slow things fast. Last summer I cut "
        "our college fest app's load time from eight seconds to two. That's why this backend role excites me — "
        "it's exactly the kind of problem I want to work on.\"",
        "example_explanation": "Present, one concrete proof, then a link to the role — in under thirty seconds.",
        "seconds": 75,
        "learn": {
            "context": "A first-round interview for an entry-level role. The interviewer opens with the classic "
            "question.",
            "partner": {
                "name": "Dana", "role": "Hiring manager", "voice": "sage", "symbol": "person.crop.square",
                "color": "#6366F1",
                "character": "Dana, a hiring manager who has heard a hundred rehearsed résumé recitals today.",
                "opening": "Thanks for coming in. So, to start — tell me about yourself.",
                "follow_up": "Ask ONE follow-up that probes their proof point: what exactly did they do, and what "
                "was the result?",
                "fallback": "That project sounds interesting. What was your part in it, specifically?",
            },
        },
        "remix": {
            "title": "Remix: the elevator version",
            "context": "You bump into a senior engineer from the company at a meetup. They ask what you're about.",
            "partner": {
                "name": "Sam", "role": "Senior engineer", "voice": "ash", "symbol": "figure.walk",
                "color": "#2F9BFF",
                "opening": "Oh, you're interviewing with us? Nice. What's your story — what are you into?",
                "follow_up": "Ask why they want to join this particular company rather than any company.",
                "fallback": "Cool. Why us, though — what drew you here?",
            },
        },
        "real": {
            "prompt": "Record your two-minute introduction once this week, or use it with a real recruiter, mentor "
            "or friend. Keep the three parts: now, proof, why this role.",
            "alt_title": "No interview soon? Introduce yourself to an AI recruiter.",
            "partner": {
                "name": "Priya", "role": "Recruiter", "voice": "coral", "symbol": "person.badge.clock",
                "color": "#9B5DE5",
                "opening": "Hi! I'm screening for a few roles this week. Give me the quick version of you.",
                "follow_up": "Ask what role they're looking for next and why.",
                "fallback": "Got it. What kind of role are you hoping for next, and why that?",
            },
            "questions": ["What proof point did you use?", "Did you link it to the role?", "What would you cut?"],
        },
    },
    {
        "title": "Tell stories that prove it",
        "dimension": "storytelling",
        "target": "Tell a STAR story (situation, task, action, result) and end with a specific result.",
        "summary": "Behavioral questions are won with one good story, not general claims.",
        "why": "Interviewers believe what you did more than what you say you are. A tight story with your own "
        "actions and a result is evidence they can repeat to the hiring committee.",
        "example": "\"Last year our app's ratings dropped after a release, and I was asked to find out why. I read two "
        "hundred reviews, traced most of them to one crash on older phones, and shipped a fix with QA in three days. "
        "Ratings went from 3.6 back to 4.4 within a month.\"",
        "example_explanation": "Situation and task in one sentence, most of the time on the actions, and a number at "
        "the end.",
        "seconds": 90,
        "learn": {
            "context": "A behavioral interview at a mid-size tech company. The interviewer asks about the hardest "
            "problem you've solved recently.",
            "partner": {
                "name": "Lauren", "role": "Hiring manager", "voice": "shimmer", "symbol": "person.crop.rectangle",
                "color": "#9B5DE5",
                "character": "Lauren, an engineering manager who has run hundreds of behavioral interviews and "
                "listens for what the candidate personally did.",
                "opening": "Tell me about the hardest problem you've solved in the last year.",
                "follow_up": "Ask what THEY personally did at the hardest moment, especially if they said 'we' a lot.",
                "fallback": "You said 'we' a few times. What did you personally do?",
            },
        },
        "remix": {
            "title": "Remix: the failure question",
            "context": "A different interviewer asks about a time something you owned went wrong.",
            "partner": {
                "name": "Ben", "role": "Senior engineer", "voice": "echo", "symbol": "exclamationmark.triangle",
                "color": "#FF8A3D",
                "character": "Ben, a senior engineer who asks about failures to see whether candidates own them.",
                "opening": "Tell me about a time something you were responsible for went wrong.",
                "follow_up": "Ask what they would do differently now, and what they changed afterwards.",
                "fallback": "Looking back, what would you do differently?",
            },
        },
        "real": {
            "prompt": "Write down three STAR stories from your work or studies — a win, a conflict and a failure — "
            "and tell one of them out loud to a friend or mentor this week.",
            "alt_title": "Tell a STAR story to an AI interviewer instead.",
            "partner": {
                "name": "Lauren", "role": "Hiring manager", "voice": "shimmer", "symbol": "person.crop.rectangle",
                "color": "#9B5DE5",
                "character": "Lauren, an engineering manager who listens for what the candidate personally did.",
                "opening": "Tell me about a time you had to learn something quickly.",
                "follow_up": "Ask for the result in numbers.",
                "fallback": "What was the result? Can you put a number on it?",
            },
            "questions": ["Which story did you tell?", "Did most of it cover your own actions?",
                          "What result did you end on?"],
        },
    },
    {
        "title": "Make the case for you",
        "dimension": "persuasion",
        "target": "Match two of your strengths to two needs of the role, each with one piece of proof.",
        "summary": "Answer \"why should we hire you?\" by connecting what you offer to what they need.",
        "why": "Generic answers (\"I'm hardworking\") sound like everyone else's. Mapping your proof to their needs "
        "makes the hiring decision easy.",
        "example": "\"You need someone who can own the onboarding flow and work closely with design. Last year I "
        "rebuilt our signup flow and cut drop-off by a third, and I ran weekly reviews with our designer the whole "
        "time. I'd bring exactly that here.\"",
        "example_explanation": "Two needs from the job description, two pieces of proof, and a confident close.",
        "seconds": 60,
        "learn": {
            "context": "Late in an interview, the hiring manager asks the classic closing question.",
            "partner": {
                "name": "Olivia", "role": "Hiring manager", "voice": "coral", "symbol": "person.crop.square",
                "color": "#E64980",
                "character": "Olivia, a hiring manager deciding between three good candidates who wants one reason "
                "to choose.",
                "opening": "We've seen some strong candidates. Why should we hire you?",
                "follow_up": "Raise one doubt about a gap in their experience and see whether they answer it with "
                "evidence.",
                "fallback": "You haven't led a team before, though. Why shouldn't that worry us?",
            },
        },
        "remix": {
            "title": "Remix: strengths and weaknesses",
            "context": "A recruiter on a screening call asks for your biggest strength and a real weakness.",
            "partner": {
                "name": "Ethan", "role": "Recruiter", "voice": "ash", "symbol": "phone", "color": "#2F9BFF",
                "character": "Ethan, a recruiter who screens dozens of candidates a week and dislikes rehearsed "
                "answers.",
                "opening": "Quick one before we wrap up: what's your biggest strength, and what's something you're "
                "working on?",
                "follow_up": "Ask how they know the weakness is actually improving.",
                "fallback": "And how do you know you're getting better at that?",
            },
        },
        "real": {
            "prompt": "Pick a real job description. Write down its top two needs and your proof for each, then say "
            "your \"why hire me\" answer out loud until it takes under a minute.",
            "alt_title": "Answer \"why should we hire you?\" for an AI hiring manager.",
            "partner": {
                "name": "Olivia", "role": "Hiring manager", "voice": "coral", "symbol": "person.crop.square",
                "color": "#E64980",
                "character": "Olivia, a hiring manager who wants one clear reason to choose a candidate.",
                "opening": "Last question from me: what makes you the right person for this role?",
                "follow_up": "Ask for one concrete example.",
                "fallback": "Can you give me one concrete example of that?",
            },
            "questions": ["Which two needs did you pick?", "What proof did you use?", "How long did your answer take?"],
        },
    },
    {
        "title": "Close the interview strong",
        "dimension": "listening",
        "target": "Ask one question that builds on something the interviewer said earlier.",
        "summary": "Your questions at the end show how well you listened.",
        "why": "\"Do you have any questions?\" is part of the test. A question that picks up something they said shows "
        "attention and genuine interest, and it's what interviewers remember.",
        "example": "\"Earlier you mentioned the team is moving to a new data platform next quarter. What would success "
        "look like for someone in this role during that move?\"",
        "example_explanation": "Refers to something specific the interviewer said, then asks an open question about it.",
        "seconds": 45,
        "learn": {
            "context": "The interview is wrapping up. Earlier, the interviewer mentioned that the team is rebuilding "
            "its mobile app.",
            "partner": {
                "name": "Sophie", "role": "Engineering manager", "voice": "sage",
                "symbol": "person.crop.circle.badge.questionmark", "color": "#10B3A3",
                "character": "Sophie, an engineering manager who mentioned earlier that her team is rebuilding its "
                "mobile app and struggling with release quality.",
                "opening": "That's all from my side. Do you have any questions for me?",
                "follow_up": "Answer their question in two sentences, including one detail they could follow up on "
                "(for example, that releases slipped twice this year), and see whether they build on it.",
                "fallback": "Good question. Honestly, our releases have slipped twice this year, so quality is a big "
                "focus.",
            },
        },
        "remix": {
            "title": "Remix: the final handshake",
            "context": "At the end of a panel interview, the chair asks whether there's anything you'd like to add.",
            "partner": {
                "name": "Robert", "role": "Panel chair", "voice": "onyx", "symbol": "hand.wave", "color": "#6366F1",
                "character": "Robert, the director chairing the panel, who values candidates who listen.",
                "opening": "Before we wrap up, is there anything you'd like to add, or anything we didn't ask?",
                "follow_up": "Answer warmly and ask what they hope the person in this role achieves in the first "
                "year.",
                "fallback": "Thanks. Anything else on your mind about the team or the role?",
            },
        },
        "real": {
            "prompt": "In your next interview or networking call, note one thing the other person says early on, and "
            "ask a question about it at the end.",
            "alt_title": "Close an interview with an AI hiring manager instead.",
            "partner": {
                "name": "Sophie", "role": "Engineering manager", "voice": "sage",
                "symbol": "person.crop.circle.badge.questionmark", "color": "#10B3A3",
                "character": "Sophie, an engineering manager whose team is hiring two more people this year.",
                "opening": "We're almost out of time. What questions do you have for me?",
                "follow_up": "Answer briefly with one detail, and see whether they build on it.",
                "fallback": "We're hiring two more people this year, so mentoring will matter a lot.",
            },
            "questions": ["What did you pick up from earlier?", "How did they react to your question?",
                          "What did you learn about the role?"],
        },
    },
]
