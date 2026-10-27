"""Extra talks for shadowing: public-domain speeches and original Comlogue scripts. Appended to ../talks.py.

Leave the list empty rather than adding anything that isn't public domain everywhere we ship (US and India) or
written for Comlogue.
"""

from __future__ import annotations

from ..talks import TalkDef

EXTRA_TALKS: tuple[TalkDef, ...] = (
    TalkDef(
        id="vivekananda_chicago",
        title="Address at the Parliament of Religions (excerpt)",
        speaker="Swami Vivekananda",
        source_note="World's Parliament of Religions, Chicago, 11 September 1893. Public domain.",
        year=1893,
        duration_label="2.5 min",
        wpm=115,
        avg_pause_seconds=1.4,
        tags=("public speaking", "warmth", "rhetoric"),
        technique="An inclusive greeting and the rhythm of repetition",
        breakdown=(
            "The opening, 'Sisters and Brothers of America', replaced the formal greeting the audience expected. "
            "Accounts say they stood and applauded for minutes before he could continue.",
            "Three 'I thank you in the name of…' lines build rhythm and a sense of scale.",
            "Parallel 'I am proud to belong to…' lines make a large idea easy to follow.",
            "One concrete image — streams meeting in the sea — carries the whole argument.",
            "He ends on hope rather than blame.",
        ),
        lines=(
            "Sisters and Brothers of America, [pause]",
            "It fills my heart with joy unspeakable to rise in response to the warm and cordial welcome which you "
            "have given us.",
            "I thank you in the name of the most ancient order of monks in the world; [pause] I thank you in the "
            "name of the mother of religions; [pause] and I thank you in the name of millions and millions of Hindu "
            "people of all classes and sects.",
            "I am proud to belong to a religion which has taught the world both tolerance and universal acceptance. "
            "[pause] We believe not only in universal toleration, but we accept all religions as true.",
            "I am proud to belong to a nation which has sheltered the persecuted and the refugees of all religions "
            "and all nations of the earth.",
            "I will quote to you, brethren, a few lines from a hymn which I remember to have repeated from my "
            "earliest boyhood, which is every day repeated by millions of human beings: [pause]",
            "“As the different streams having their sources in different places all mingle their water in the sea, "
            "[pause] so, O Lord, the different paths which men take through different tendencies, various though "
            "they appear, crooked or straight, all lead to Thee.”",
            "Sectarianism, bigotry, and its horrible descendant, fanaticism, have long possessed this beautiful "
            "earth. [pause] They have filled the earth with violence, drenched it often and often with human blood, "
            "destroyed civilisation and sent whole nations to despair.",
            "Had it not been for these horrible demons, human society would be far more advanced than it is now.",
            "But their time is come; [pause] and I fervently hope that the bell that tolled this morning in honour "
            "of this convention may be the death-knell of all fanaticism, [pause] of all persecutions with the sword "
            "or with the pen, [pause] and of all uncharitable feelings between persons wending their way to the "
            "same goal.",
        ),
        tts_voice="cedar",
        tts_instructions=(
            "Voice: measured, resonant and warm, with a dignified Indian English accent. Pace: slow, about 115 "
            "words per minute. Hold a full pause at each ellipsis. Let the opening greeting ring out with warmth, "
            "and build gently through each 'I thank you' and 'I am proud' line."
        ),
    ),
    TalkDef(
        id="placement_intro",
        title="A placement introduction that stands out",
        speaker="Comlogue exemplar · final-year engineering student",
        source_note="Original script written for Comlogue.",
        year=None,
        duration_label="1 min",
        wpm=140,
        avg_pause_seconds=0.9,
        tags=("interviews", "structure"),
        technique="Present, proof, purpose",
        breakdown=(
            "The first line says who she is today, in plain words, instead of reciting her résumé.",
            "One proof point with a number does the work of ten adjectives.",
            "She names what the project taught her, which shows self-awareness.",
            "The close links her story to this specific role — and then she stops.",
        ),
        lines=(
            "Good morning. [pause] I'm Ananya, a final-year electronics student [pause] who ended up loving software.",
            "In my third year, [pause] our college canteen's token system kept crashing at lunchtime.",
            "Two friends and I rebuilt it as a small web app. [pause] The queue went from fifteen minutes to four, "
            "[pause] and the canteen still uses it.",
            "That project taught me something: [pause] I enjoy the messy part — talking to the canteen staff, "
            "[pause] and finding out what actually slows them down.",
            "Since then, I've interned at a logistics startup, [pause] where I built the dashboard their operations "
            "team checks every morning.",
            "That's why this role excites me. [pause] Your team builds tools that people use under pressure, "
            "[pause] and that's exactly the kind of problem I want to solve.",
            "Thank you.",
        ),
        tts_voice="coral",
        tts_instructions=(
            "Voice: confident young woman in her early twenties with an Indian English accent. Pace: clear and "
            "steady, about 140 words per minute. Short pause at each ellipsis. Warm and sincere, never rehearsed."
        ),
    ),
    TalkDef(
        id="client_delay_call",
        title="Owning a delay on a US client call",
        speaker="Comlogue exemplar · project lead at an IT services firm",
        source_note="Original script written for Comlogue.",
        year=None,
        duration_label="1 min",
        wpm=135,
        avg_pause_seconds=1.0,
        tags=("meetings", "clarity", "client calls"),
        technique="Own it, explain it, fix it",
        breakdown=(
            "He names the problem in the first sentence instead of warming up with apologies.",
            "The cause gets one plain-English sentence, with no blame and no internal jargon.",
            "A new date, a reason to trust it and an interim option give the client something to take to their boss.",
            "One apology, after the facts, sounds sincere rather than nervous.",
        ),
        lines=(
            "Hi Kevin, thanks for making time. [pause] I'll get straight to it: [pause] the reporting module won't "
            "be ready this Friday.",
            "Here's why. [pause] Your new data feed arrives in a different format from the one we tested, [pause] "
            "and two of the reports break on it.",
            "That's on us — [pause] we should have tested with live data earlier.",
            "Here's the plan. [pause] We'll have the fix by next Wednesday, your time, [pause] and we're already "
            "testing with yesterday's live feed.",
            "In the meantime, [pause] the three reports your VP uses every Monday will be ready this Friday, as "
            "planned.",
            "From now on, [pause] we'll test every release against a live data sample before we commit to a date.",
            "I'm sorry for the change. [pause] What questions can I answer for your VP?",
        ),
        tts_voice="ash",
        tts_instructions=(
            "Voice: calm, accountable project lead in his thirties with an Indian English accent. Pace: measured, "
            "about 135 words per minute. Pause at each ellipsis. Steady and sincere; no nervous rushing."
        ),
    ),
)
