"""Offline demo provider: deterministic, realistic, and clearly flagged as demo output.

It cannot hear audio, so transcripts are canned (per activity/mission/persona) unless a test passes
`mock_transcript`. Everything downstream — quality gates, evidence caps, partial profiles, speaker
confirmation — runs for real. Diarization is simulated from the actual audio (energy VAD + pitch/MFCC
clustering), so different voices really do get different labels.
"""

from __future__ import annotations

import re

import numpy as np

from ..audio import ffmpeg, quality, voiceprint
from ..audio.speech_stats import filler_counts, hedge_count, sentence_word_counts
from ..domain.activities import ACTIVITIES
from ..domain.evidence import Unit
from .llm_schemas import (
    AssessmentJudgement,
    AttemptJudgement,
    CustomScenario,
    DebriefJudgement,
    DimensionJudgement,
    EventPrep,
    EvidenceRef,
    GroupLine,
    GroupReply,
    MomentumNote,
    PartnerReply,
    PrepItemJudgement,
    ReflectionReply,
    Rewrite,
    SparJudgement,
    SparObservation,
    StyleJudgement,
    WeeklyJudgement,
)
from .provider import AIProvider
from .types import (
    AssessmentRequest,
    AttemptRequest,
    AudioHint,
    CustomScenarioRequest,
    DebriefRequest,
    DiarizationResult,
    DiarizedSegment,
    EventPrepRequest,
    GroupReplyRequest,
    KnownSpeaker,
    PartnerReplyRequest,
    ReflectionRequest,
    SparRequest,
    TranscriptionResult,
    WeeklyRequest,
)

MISSION_ANSWERS = (
    "I'd recommend we go with the second option. It's cheaper over the year, and the team already knows how it "
    "works. What would you want to check before we commit?",
    "That's a fair concern. They've done three migrations like ours this year, so I'd still go with them — could "
    "we agree on a two-week trial and decide after that?",
)
SPAR_ANSWERS = (
    "I think it's, um, kind of going to pay back pretty fast, because the team is really stretched right now.",
    "Fair. It pays back in seven months: we cut contractor spend by forty thousand a month.",
    "If it slips, we stop after the first phase. You'd risk a hundred and twenty thousand, not four hundred.",
    "So I'm asking for approval of phase one today, with a review in ninety days.",
    "Yes — and I'll send you the numbers in writing this afternoon.",
    "Thanks for pushing on it. It made the plan better.",
)
DAILY_ANSWERS = (
    "Okay, so the short version: I help a team of twelve ship our app every two weeks. Think of it like running a "
    "kitchen — I make sure the right dishes go out on time, and nobody gets burned.",
    "Let me try that again. My job is making sure our app ships on time. Every two weeks, twelve people, one "
    "release — I'm the one who keeps it moving.",
)
GROUP_ANSWERS = (
    "Can I add a different angle? I think the real question is which work needs people in the same room. "
    "Mentoring freshers does, but focused coding often doesn't.",
    "Building on what Ananya said about commute time — in Bengaluru that's two hours a day. A hybrid plan with "
    "three office days for new joiners could give us both.",
    "Karthik, you mentioned attrition earlier — what did you see in the numbers?",
    "So to summarise: we agree freshers need office time, and most of us think a hybrid model works for "
    "experienced staff. That's our conclusion.",
)
_GD_REACTIONS = (
    "I hear you, but I'm not fully convinced — {kw} sounds good on paper, but who checks that it actually works?",
    "Adding to that: {kw} matters, but it depends a lot on the team and the city.",
    "Sorry, can I come in here? I see it a little differently. What about the people who've just joined?",
    "That's a fair point about {kw}. I'd also look at what it costs the company.",
)
_PANEL_QUESTIONS = (
    "Thanks. Can you give us a specific example of that?",
    "Let me push on that a little — what was your own contribution, as opposed to the team's?",
    "Interesting. How did you measure whether it worked?",
    "And if you had to do it again, what would you change?",
)
MEETING_USER_LINES = (
    "So I think the main question today is whether we launch the new onboarding before the holidays.",
    "My recommendation is to launch on the fifteenth, behind a flag, for ten percent of new users.",
    "Two reasons: support is ready, and the flag means we can roll back in minutes.",
    "Lin, you've looked at the drop-off data — what are we missing?",
    "Okay, that's a good point. Let's fix the export step first, then launch.",
    "So, to recap, we launch on the fifteenth, Ravi owns the rollback plan, and I'll update the timeline.",
)
MEETING_OTHER_LINES = (
    "Sounds good. Where are we on the onboarding numbers?",
    "Honestly I'm worried about the export step. A lot of people drop off there.",
    "From the data, about a third of new users never finish the export.",
    "If we fix that first, I'm comfortable launching on the fifteenth.",
    "I can own the rollback plan.",
    "Works for me. Let's do it.",
)
_STOPWORDS = {
    "about", "after", "again", "because", "before", "being", "could", "every", "honestly", "really", "should",
    "something", "their", "there", "these", "thing", "things", "think", "those", "through", "would", "lately",
    "basically", "actually", "pretty", "kind", "spending", "started", "probably",
}
_PERSUASION_MARKERS = ("should", "let's", "we could", "how about", "recommend", "what if", "worth", "you'd love",
                       "i'd go with", "instead")
_STORY_MARKERS = ("then", "when i", "so i", "last year", "one time", "ended up", "the second", "suddenly")
_WARM_MARKERS = ("thanks", "love", "sounds", "that's great", "sorry", "i hear", "makes sense", "lovely", "glad")


def _first_sentence(text: str, max_words: int = 25) -> str:
    sentence = re.split(r"(?<=[.!?])\s+", text.strip())[0]
    words = sentence.split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")


def _keyword(text: str) -> str | None:
    words = [w.strip(".,!?;:'\"").lower() for w in text.split()]
    candidates = [w for w in words if len(w) >= 6 and w.isalpha() and w not in _STOPWORDS]
    return max(candidates, key=len) if candidates else None


def _clean(text: str) -> str:
    cleaned = re.sub(r"\b(um+|uh+|erm|you know|i mean|kind of|sort of|i think|i guess|basically|pretty)\b,?\s*",
                     "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else text


class MockProvider(AIProvider):
    name = "mock"
    demo = True

    # ------------------------------------------------------------------ audio

    def transcribe(self, audio_path: str, *, language: str, prompt: str | None, hint: AudioHint) -> TranscriptionResult:
        if hint.mock_text:
            return TranscriptionResult(text=hint.mock_text, avg_logprob=-0.12, low_confidence_ratio=0.02, model="mock")
        parts = hint.context_key.split(":")
        text = "That's a good question. Let me think about the main point I'd want to make here."
        if parts[0] == "assessment" and len(parts) > 1 and parts[1] in ACTIVITIES:
            answers = ACTIVITIES[parts[1]].demo_answers
            if answers:
                text = answers[min(hint.turn_index, len(answers) - 1)]
        elif parts[0] == "mission":
            text = MISSION_ANSWERS[min(hint.turn_index, len(MISSION_ANSWERS) - 1)]
        elif parts[0] == "spar":
            text = SPAR_ANSWERS[min(hint.turn_index, len(SPAR_ANSWERS) - 1)]
        elif parts[0] == "daily":
            text = DAILY_ANSWERS[min(hint.turn_index, len(DAILY_ANSWERS) - 1)]
        elif parts[0] == "group":
            text = GROUP_ANSWERS[min(hint.turn_index, len(GROUP_ANSWERS) - 1)]
        return TranscriptionResult(text=text, avg_logprob=-0.15, low_confidence_ratio=0.03, model="mock")

    def diarize(
        self, audio_path: str, *, language: str, known_speakers: list[KnownSpeaker], hint: AudioHint
    ) -> DiarizationResult:
        samples = ffmpeg.read_wav(hint.wav_path) if hint.wav_path else self._decode(audio_path)
        duration = len(samples) / ffmpeg.SAMPLE_RATE
        report = quality.analyze(samples, min_speech_seconds=0.5)
        spans = self._segments_from_runs(report.speech_runs)
        if not spans:
            return DiarizationResult(segments=[], duration=duration, model="mock", used_references=bool(known_speakers))

        prints = [voiceprint.voiceprint(ffmpeg.segment_samples(samples, a, b)) for a, b in spans]
        labels = self._cluster(prints)
        # Rename clusters that match a known speaker reference.
        rename: dict[str, str] = {}
        for known in known_speakers:
            ref = voiceprint.voiceprint(ffmpeg.read_wav(known.wav_path))
            best_label, best_score = None, 0.0
            for label in sorted(set(labels)):
                idx = [i for i, lab in enumerate(labels) if lab == label]
                pieces = [ffmpeg.segment_samples(samples, *spans[i]) for i in idx[:8]]
                cluster_print = voiceprint.voiceprint(np.concatenate(pieces)) if pieces else {}
                score = voiceprint.similarity(ref, cluster_print) or 0.0
                if score > best_score:
                    best_label, best_score = label, score
            if best_label is not None and best_score >= voiceprint.WEAK_MATCH and best_label not in rename:
                rename[best_label] = known.name
        user_label = next(iter(rename), None) or (labels[0] if labels else None)
        segments: list[DiarizedSegment] = []
        counters = {"user": 0, "other": 0}
        for (start, end), label in zip(spans, labels, strict=True):
            role = "user" if label == user_label else "other"
            lines = MEETING_USER_LINES if role == "user" else MEETING_OTHER_LINES
            text = lines[counters[role] % len(lines)]
            counters[role] += 1
            segments.append(DiarizedSegment(speaker=rename.get(label, label), start=start, end=end, text=text))
        return DiarizationResult(segments=segments, duration=duration, model="mock",
                                 used_references=bool(known_speakers))

    def synthesize(self, text: str, *, voice: str, instructions: str | None) -> bytes | None:
        return None  # the app speaks partner lines on-device in demo mode

    @staticmethod
    def _decode(path: str) -> np.ndarray:
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, "a.wav")
            ffmpeg.decode_to_wav16k(path, wav)
            return ffmpeg.read_wav(wav)

    @staticmethod
    def _segments_from_runs(runs: list[tuple[float, float]]) -> list[tuple[float, float]]:
        spans: list[tuple[float, float]] = []
        for start, end in runs:
            if spans and start - spans[-1][1] < 0.45 and end - spans[-1][0] < 12.0:
                spans[-1] = (spans[-1][0], end)
            else:
                spans.append((start, end))
        return [(round(a, 2), round(b, 2)) for a, b in spans if b - a >= 0.6]

    @staticmethod
    def _cluster(prints: list[dict]) -> list[str]:
        """Greedy clustering on pitch first, MFCC similarity as a tie-breaker."""
        centroids: list[dict] = []
        labels: list[str] = []
        for vp in prints:
            best, best_score = None, 0.0
            for idx, centroid in enumerate(centroids):
                f0_a, f0_b = vp.get("f0_median"), centroid.get("f0_median")
                if f0_a and f0_b:
                    score = 1.0 - abs(f0_a - f0_b) / max(f0_a, f0_b)
                else:
                    score = voiceprint.similarity(vp, centroid) or 0.0
                if score > best_score:
                    best, best_score = idx, score
            if best is not None and best_score >= 0.85:
                labels.append(chr(ord("A") + best))
            elif best is not None and len(centroids) >= 4:
                labels.append(chr(ord("A") + best))
            else:
                centroids.append(vp)
                labels.append(chr(ord("A") + len(centroids) - 1))
        return labels

    # ------------------------------------------------------------------ language

    def partner_reply(self, req: PartnerReplyRequest) -> PartnerReply:
        last_user = next((text for speaker, text in reversed(req.history) if speaker == "USER"), "")
        reply = req.fallback_line
        if req.step_key == "ask_detail":
            word = _keyword(last_user)
            if word:
                reply = f"Oh nice — {word}? What got you into that?"
        elif req.step_key == "respond":
            advice = any(marker in last_user.lower() for marker in ("you should", "just ", "try ", "why don't you"))
            if not advice:
                reply = (
                    "Yeah, exactly. I think I worried the idea was obvious and I'd look silly in front of everyone."
                )
        elif req.step_key == "clarify":
            word = _keyword(last_user)
            if word:
                reply = f"Wait, sorry — what does \"{word}\" actually mean?"
        if req.kind != "spar":
            return PartnerReply(reply=reply, end_conversation=req.is_closing, coach_whisper=None, momentum=None,
                                outcome_label=None)
        # Spar: simple, deterministic negotiation dynamics.
        user_turns = sum(1 for speaker, _ in req.history if speaker == "USER")
        hedges = hedge_count(last_user, "en") + sum(filler_counts(last_user, "en").values())
        has_number = bool(re.search(r"\d|percent|thousand|million|months?|weeks?", last_user.lower()))
        momentum = min(1.0, max(0.0, 0.25 + 0.17 * user_turns + (0.15 if has_number else 0) - 0.08 * hedges))
        if hedges:
            whisper = "You're hedging — drop \"I think\" and lead with your point."
        elif not has_number:
            whisper = "Make it concrete: give a number, a date or an example."
        elif len(last_user.split()) > 70:
            whisper = "Shorter: one point, one reason, then stop."
        else:
            whisper = "Good. Now ask clearly for what you want."
        resolved = req.is_closing or momentum >= 0.8 or req.turns_left <= 0
        if resolved:
            agreed = momentum >= 0.6
            reply = "Alright. You've got a deal — send me the details." if agreed else (
                "I'm not convinced yet. Come back when you have numbers I can defend."
            )
            outcome = "Agreed" if agreed else "Not convinced yet"
            return PartnerReply(reply=reply, end_conversation=True, coach_whisper=whisper, momentum=momentum,
                                outcome_label=outcome)
        pushback = (
            "Pretty fast isn't a number. Give me a number.",
            "And if it slips? What's my downside?",
            "Okay. What exactly are you asking me to approve today?",
            "Hm. Why now and not next quarter?",
        )
        reply = pushback[(user_turns - 1) % len(pushback)] if user_turns else req.fallback_line
        return PartnerReply(reply=reply, end_conversation=False, coach_whisper=whisper, momentum=momentum,
                            outcome_label=None)

    def group_reply(self, req: GroupReplyRequest) -> GroupReply:
        moderator = next((m for m in req.members if m.is_moderator), req.members[0])
        others = [m for m in req.members if not m.is_moderator] or [moderator]
        user_turns = sum(1 for speaker, _ in req.history if speaker == "USER")
        last_user = next((text for speaker, text in reversed(req.history) if speaker == "USER"), "")
        word = _keyword(last_user)
        if word:  # keep the word as they said it ("Bengaluru", not "bengaluru")
            word = next((raw.strip(".,!?;:'\"") for raw in last_user.split()
                         if raw.strip(".,!?;:'\"").lower() == word), word)
        word = word or "that"
        if req.is_closing:
            closing = ("Thank you — that's all our questions. We'll be in touch soon."
                       if req.panel_kind == "panel_interview" else "Thank you, everyone. Time's up — good discussion.")
            return GroupReply(lines=[GroupLine(speaker_id=moderator.id, text=closing)], end_discussion=True)
        first = others[(user_turns - 1) % len(others)]
        if req.panel_kind == "panel_interview":
            lines = [GroupLine(speaker_id=first.id, text=_PANEL_QUESTIONS[(user_turns - 1) % len(_PANEL_QUESTIONS)])]
        else:
            lines = [GroupLine(speaker_id=first.id,
                               text=_GD_REACTIONS[(user_turns - 1) % len(_GD_REACTIONS)].format(kw=word))]
            if user_turns % 2 == 0 and len(others) > 1:  # every other turn, a second voice joins in
                second = others[user_turns % len(others)]
                if second.id != first.id:
                    lines.append(GroupLine(speaker_id=second.id, text="Partly agree. But let's not forget the "
                                           "practical side — someone has to make it work day to day."))
        return GroupReply(lines=lines, end_discussion=False)

    def assess(self, req: AssessmentRequest) -> AssessmentJudgement:
        user_units = [u for u in req.units if u.usable_user]
        all_user_text = " ".join(u.text for u in user_units)
        sentences = sentence_word_counts(all_user_text)
        avg_sentence = sum(sentences) / len(sentences) if sentences else 0
        minutes = max(req.stats.user_speech_seconds / 60, 0.1)
        fillers_pm = sum(filler_counts(all_user_text, req.language).values()) / minutes
        avg_turn_words = req.stats.user_words / max(1, req.stats.user_turns)
        questions_after_partner = sum(
            1 for prev, cur in zip(req.units, req.units[1:], strict=False)
            if prev.role != "user" and cur.usable_user and "?" in cur.text
        )
        lowered = all_user_text.lower()

        def level_for(dim: str) -> int:
            level = 3
            if dim == "clarity":
                level += 1 if 8 <= avg_sentence <= 22 else 0
                level -= 1 if fillers_pm > 6 else 0
            elif dim == "structure":
                level += 1 if req.stats.extended_turns >= 2 and any(
                    s in lowered for s in ("first", "then", "so ", "the main", "finally")) else 0
            elif dim == "listening":
                level += 1 if questions_after_partner >= 1 else -1
            elif dim == "warmth":
                level += 1 if any(m in lowered for m in _WARM_MARKERS) else 0
            elif dim == "persuasion":
                level += 1 if "because" in lowered or "so you" in lowered else 0
                level += 0 if any(m in lowered for m in ("what if", "instead", "how about")) else -1
            elif dim == "concision":
                level += -1 if avg_turn_words > 110 else (1 if avg_turn_words < 55 else 0)
            elif dim == "storytelling":
                level += 1 if any(m in lowered for m in ("learned", "taught me", "now every", "ever since")) else 0
            # Small fixed per-dimension offsets so demo profiles have a realistic, uneven shape.
            level += {"structure": -1, "persuasion": -1, "concision": -1}.get(dim, 0)
            return max(1, min(5, level))

        def has_opportunity(dim: str) -> bool:
            if dim == "persuasion":
                return "make_a_case" in req.stats.activities or any(m in lowered for m in _PERSUASION_MARKERS)
            if dim == "storytelling":
                return "tell_a_story" in req.stats.activities or (
                    req.stats.narrative_turns >= 1 and any(m in lowered for m in _STORY_MARKERS)
                )
            return True

        def evidence_for(dim: str) -> list[EvidenceRef]:
            ranked = sorted(user_units, key=lambda u: (-self._relevance(dim, u), -u.words))
            refs = []
            for unit in ranked[:2]:
                refs.append(EvidenceRef(segment_id=unit.uid, quote=_first_sentence(unit.text, 22),
                                        note=self._note(dim)))
            return refs

        judgements: list[DimensionJudgement] = []
        for dim, cap in req.caps.items():
            if cap.max_strength == "none" or not has_opportunity(dim):
                judgements.append(DimensionJudgement(
                    dimension=dim, opportunity_found=False, opportunity_note=cap.reason or "No clear opportunity.",
                    evidence_strength="none", level=None, confidence=None, summary=None, strengths=[],
                    one_change=None, evidence=[], missing_reason=cap.reason,
                ))
                continue
            level = level_for(dim)
            judgements.append(DimensionJudgement(
                dimension=dim, opportunity_found=True, opportunity_note="Present in this sample.",
                evidence_strength=cap.max_strength, level=level,
                confidence="moderate" if cap.max_strength == "sufficient" else "low",
                summary=self._summary(dim, level), strengths=[self._strength(dim)], one_change=self._change(dim),
                evidence=evidence_for(dim), missing_reason=None,
            ))

        first_win = None
        if any(j.evidence_strength != "none" for j in judgements):
            best: tuple[int, Unit, str] | None = None
            for unit in user_units:
                for sentence in re.split(r"(?<=[.!?])\s+", unit.text.strip()):
                    weight = hedge_count(sentence, "en") + sum(filler_counts(sentence, "en").values())
                    if weight and (best is None or weight > best[0]):
                        best = (weight, unit, sentence)
            if best is not None:
                _, unit, sentence = best
                said = " ".join(sentence.split()[:30])
                cleaned = _clean(said)
                if cleaned != said:
                    first_win = Rewrite(
                        segment_id=unit.uid, dimension="concision", you_said=said, try_instead=cleaned,
                        why="Without the warm-up words, your point lands first and sounds more certain.",
                    )

        style = StyleJudgement(eligible=False, archetype=None, description=None, traits=[])
        if req.style_eligible:
            if questions_after_partner >= 2:
                archetype = "The Connector"
            elif req.stats.narrative_turns >= 2:
                archetype = "The Storyteller"
            elif avg_turn_words < 45:
                archetype = "The Straight Shooter"
            else:
                archetype = "The Explainer"
            style = StyleJudgement(
                eligible=True, archetype=archetype,
                description="In these conversations you tended to explain with examples and bring the other person "
                "along. This is an early read from a few short samples.",
                traits=["Uses concrete examples", "Checks in with the listener"],
            )
        assessed = [j for j in judgements if j.evidence_strength != "none"]
        headline = "Here's what stood out" if assessed else "Not enough to go on yet"
        summary = (
            "In this sample you made your points with concrete examples. The details below show the moments we "
            "used." if assessed else "We didn't hear enough to describe your communication yet."
        )
        return AssessmentJudgement(dimensions=judgements, headline=headline, summary=summary, first_win=first_win,
                                   style=style)

    @staticmethod
    def _relevance(dim: str, unit: Unit) -> int:
        text = unit.text.lower()
        if dim == "listening":
            return text.count("?") + text.count("sounds") + text.count("so it")
        if dim == "persuasion":
            return sum(text.count(m) for m in _PERSUASION_MARKERS)
        if dim == "storytelling":
            return sum(text.count(m) for m in _STORY_MARKERS)
        if dim == "warmth":
            return sum(text.count(m) for m in _WARM_MARKERS)
        return 0

    @staticmethod
    def _note(dim: str) -> str:
        return {
            "clarity": "Your main point is easy to find here.",
            "structure": "A recognizable shape you can build on.",
            "listening": "You responded to what was said.",
            "warmth": "You showed interest in the other person.",
            "persuasion": "Your case and how you adapted.",
            "concision": "How quickly you got to the point.",
            "storytelling": "Where your story came to life.",
        }[dim]

    @staticmethod
    def _summary(dim: str, level: int) -> str:
        base = {
            "clarity": "In this sample your main point was usually easy to follow",
            "structure": "In this sample your longer answers had a recognizable shape",
            "listening": "In this conversation you picked up on what Maya said",
            "warmth": "In this conversation you came across as friendly and interested",
            "persuasion": "When you made your case, you gave a reason that fit the listener",
            "concision": "You mostly got to the point, with some warm-up before it",
            "storytelling": "Your story had a clear setup and a memorable turn",
        }[dim]
        return base + ("." if level >= 3 else ", with room to make it land faster.")

    @staticmethod
    def _strength(dim: str) -> str:
        return {
            "clarity": "Concrete examples made the idea easy to picture.",
            "structure": "You ended with a clear takeaway.",
            "listening": "You asked a follow-up about something specific.",
            "warmth": "You acknowledged how the other person felt.",
            "persuasion": "You adapted when you heard the objection.",
            "concision": "Short sentences in your best answers.",
            "storytelling": "A specific, vivid detail.",
        }[dim]

    @staticmethod
    def _change(dim: str) -> str:
        return {
            "clarity": "Say the main point in your first sentence, then add the example.",
            "structure": "Signpost your answer: 'Two things — first…, second…'.",
            "listening": "Before offering advice, reflect back what you heard in one sentence.",
            "warmth": "Use the other person's name or words when you respond.",
            "persuasion": "Name what's in it for them before you share your reasons.",
            "concision": "Cut the warm-up phrase and start with your answer.",
            "storytelling": "Start in the moment: time, place, action.",
        }[dim]

    def attempt_feedback(self, req: AttemptRequest) -> AttemptJudgement:
        user_units = [u for u in req.units if u.usable_user]
        if not user_units:
            return AttemptJudgement(
                assessable="no", target_met="unclear", headline="We couldn't hear enough of your answer this time.",
                where_segment_id=None, where_quote=None, where_note=None, what_worked=[], one_change=None,
                missing_evidence="We need a clear answer to the situation to give feedback.",
                comparison_summary=None, comparison_changes=[],
            )
        first = user_units[0]
        text = " ".join(u.text for u in user_units).lower()
        met = "yes" if ("because" in text or "reason" in text or "," in first.text) and "?" in text else (
            "partly" if len(text.split()) >= 20 else "no")
        # Mission copy talks about recommendations; other targets (daily reps) get neutral copy.
        recommend = "recommend" in f"{req.target_behavior} {req.mission_title}".lower()
        comparison_summary, changes = None, []
        if req.previous_units:
            prev_first = next((u for u in req.previous_units if u.usable_user), None)
            prev_words = len(prev_first.text.split()) if prev_first else 0
            comparison_summary = (
                f"This time your first answer was {len(first.text.split())} words (before: {prev_words}). "
                + ("You stated your recommendation earlier and kept both reasons." if recommend
                   else "The target came through earlier and more clearly.")
            )
            changes = (["Recommendation moved into the first sentence", "Ended with a question that invites a response"]
                       if recommend else ["Main point moved earlier", "One concrete example instead of several"])
        if recommend:
            headline = ("Your recommendation came early — that's the core of this skill." if met != "no"
                        else "Good start — now bring the recommendation forward.")
            note, worked = "Where your recommendation appears.", "You gave a concrete reason the listener cares about."
            change = "Name the second reason before you invite a response."
        else:
            headline = ("The target showed up in your answer — nice." if met != "no"
                        else "Good start — now aim straight for the target.")
            note, worked = "Where the target showed up.", "You kept it specific and easy to follow."
            change = "Try it once more and open with your main point."
        return AttemptJudgement(
            assessable="yes" if all(not u.excluded for u in req.units if u.role == "user") else "partly",
            target_met=met, headline=headline,
            where_segment_id=first.uid, where_quote=_first_sentence(first.text, 20), where_note=note,
            what_worked=[worked], one_change=change,
            missing_evidence=None, comparison_summary=comparison_summary, comparison_changes=changes,
        )

    def spar_report(self, req: SparRequest) -> SparJudgement:
        user_units = [u for u in req.units if u.usable_user]
        if req.kind == "group":
            return self._group_report(req, user_units)
        final = req.momentum[-1][1] if req.momentum else 0.4
        label = "Agreed" if final >= 0.6 else "Not convinced yet"
        notes = [MomentumNote(turn_index=i, note="Momentum rose after you named a specific number.")
                 for i, v in req.momentum[1:2]]
        moments = []
        for unit in sorted(user_units, key=lambda u: -(hedge_count(u.text, "en")))[:1]:
            said = _first_sentence(unit.text, 25)
            moments.append(Rewrite(segment_id=unit.uid, dimension="persuasion", you_said=said,
                                   try_instead=_clean(said), why="A direct claim sounds more credible."))
        observations = []
        if user_units:
            observations.append(SparObservation(dimension="persuasion", note="You got more specific as the "
                                                "conversation went on.", segment_id=user_units[-1].uid))
        return SparJudgement(
            outcome_label=label,
            outcome_detail=f"{req.persona_name} responded best when you gave concrete numbers.",
            momentum_notes=notes, moments=moments, observations=observations,
            next_step="Open with the number next time, then the reason.",
        )

    @staticmethod
    def _group_report(req: SparRequest, user_units: list[Unit]) -> SparJudgement:
        text = " ".join(u.text for u in user_units).lower()
        built_on = any(m in text for m in ("building on", "adding to", "you mentioned", "said about", "agree with"))
        summarised = any(m in text for m in ("to summarise", "to summarize", "so to sum", "our conclusion"))
        invited = "?" in text
        label = "Strong contributor" if built_on and (summarised or invited) else "Good entry, room to build"
        moments = []
        for unit in user_units[:1]:
            said = _first_sentence(unit.text, 25)
            moments.append(Rewrite(segment_id=unit.uid, dimension="structure", you_said=said,
                                   try_instead="My point is simple: " + _clean(said)[:1].lower() + _clean(said)[1:],
                                   why="Naming your point first makes it easy for the group to build on it."))
        observations = []
        if built_on and user_units:
            observations.append(SparObservation(dimension="listening", note="You built on what others said "
                                                "instead of repeating your own point.", segment_id=user_units[-1].uid))
        if invited and user_units:
            observations.append(SparObservation(dimension="warmth", note="You invited a quieter participant in.",
                                                segment_id=user_units[0].uid))
        focus = req.evaluation_focus[0].lower() if req.evaluation_focus else "entering the discussion"
        return SparJudgement(
            outcome_label=label,
            outcome_detail=f"You did well on {focus}; the group picked up your points.",
            momentum_notes=[], moments=moments, observations=observations,
            next_step="Next time, offer a one-sentence summary before the moderator closes.",
        )

    def reflection_reply(self, req: ReflectionRequest) -> ReflectionReply:
        opener = {
            "well": "That's great — trying it in a real conversation is the hardest part.",
            "mixed": "Thanks for trying it for real — mixed results are normal the first few times.",
            "hard": "Thanks for trying — it's genuinely hard the first time, and you did it anyway.",
        }.get(req.went or "", "Thanks for trying it in a real conversation.")
        return ReflectionReply(reply=f"{opener} Next time, aim for just the first part of the target: "
                                     f"{req.target_behavior.split(',')[0].lower()}.")

    def event_prep(self, req: EventPrepRequest) -> EventPrep:
        role = {
            "interview": "Interviewer", "meeting": "Colleague", "presentation": "Audience member",
            "social": "New acquaintance", "negotiation": "Counterpart", "placement": "HR interviewer",
            "group_discussion": "Fellow candidate", "client_call": "Client", "viva": "Examiner",
            "appraisal": "Your manager",
        }.get(req.kind, "Conversation partner")
        title = req.title
        return EventPrep(items=[
            PrepItemJudgement(title="Warm-up", scenario=f"A friendly run-through of the start of '{title}'.",
                              partner_role=role, difficulty="kind"),
            PrepItemJudgement(title="The realistic version",
                              scenario=f"'{title}' as it will most likely go, including one tricky question.",
                              partner_role=role, difficulty="real"),
            PrepItemJudgement(title="The tough moment",
                              scenario=f"The hardest part of '{title}': someone pushes back hard.",
                              partner_role=role, difficulty="brutal"),
        ])

    def weekly(self, req: WeeklyRequest) -> WeeklyJudgement:
        highlights = req.facts[:3] or ["A quiet week — that's okay."]
        return WeeklyJudgement(highlights=highlights,
                               message=f"Next up: {req.focus_title}. One short session is enough to keep going.")

    def debrief(self, req: DebriefRequest) -> DebriefJudgement:
        user_units = [u for u in req.units if u.usable_user]
        best = max(user_units, key=lambda u: u.words) if user_units else None
        decisions = [u.text for u in req.units if re.search(r"\b(let's|we'll|agreed|decided|we launch)\b",
                                                             u.text.lower())][:3]
        user_share = next((s for _, s, is_user in req.talk_share if is_user), 0.0)
        return DebriefJudgement(
            best_moment_segment_id=best.uid if best else None,
            best_moment_note="You made a clear recommendation with reasons." if best else None,
            decisions=decisions,
            follow_up_summary="Thanks, everyone — quick recap: " + "; ".join(decisions[:2]) if decisions else None,
            one_thing_to_try="Ask one quieter person for their view before giving yours."
            if user_share > 0.5 else "Summarize the decision out loud before the meeting ends.",
        )

    def custom_scenario(self, req: CustomScenarioRequest) -> CustomScenario:
        scenario = req.scenario.strip().rstrip(".")
        return CustomScenario(
            partner_name="Jordan", partner_role="Conversation partner",
            opening_line="Okay, I've got a few minutes. What did you want to talk about?",
            context=f"Practice: {scenario}.",
            character="Jordan is busy but fair, and responds well to clear, specific asks.",
            win_condition="A clear ask with a concrete reason and some flexibility.",
        )
