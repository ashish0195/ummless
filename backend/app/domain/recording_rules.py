"""Recording-consent rules by region. General information, not legal advice — legal should review.

Product policy is stricter than every rule below: Comlogue always asks that *everyone* in the
conversation agrees to be recorded. The regional note gives context; it is never a loophole.
"""

from __future__ import annotations

from ..schemas import CodeName, RecordingRules

POLICY = "Comlogue requires everyone in the conversation to agree to be recorded, wherever you are."
DISCLAIMER = (
    "This is general information, not legal advice. Rules can differ for phone calls, workplaces and "
    "public places, and they change over time."
)
HOW_TO_ASK = (
    "\"Mind if I record this? I'm using an app to get feedback on how I communicate. It's just for me, "
    "and I can delete it anytime.\""
)

US_STATES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

# All-party consent for private conversations (interpretations vary; MI and DE are commonly listed here).
ALL_PARTY = {"CA", "DE", "FL", "IL", "MD", "MA", "MI", "MT", "NH", "PA", "WA"}
MIXED: dict[str, str] = {
    "CT": "Connecticut generally requires everyone's consent to record phone and electronic calls, while "
    "in-person conversations follow a one-party rule.",
    "NV": "Nevada courts require everyone's consent for phone calls; in-person conversations follow a "
    "one-party rule.",
    "OR": "Oregon requires everyone to be told before an in-person conversation is recorded; phone calls "
    "follow a one-party rule.",
}
NO_STATUTE = {"VT": "Vermont has no specific recording statute, so it's especially important to ask."}

COUNTRIES: dict[str, tuple[str, str, str, str]] = {
    # code: (name, rule, headline, detail)
    "CA": ("Canada", "one_party",
           "One-party consent in Canada",
           "You can generally record a conversation you take part in, but privacy law still expects you to be "
           "open about it — ask first."),
    "GB": ("United Kingdom", "mixed",
           "Ask first in the UK",
           "Recording your own conversation for personal use is generally allowed, but data-protection law "
           "(UK GDPR) treats voices as personal data once shared or stored. Ask everyone first."),
    "IE": ("Ireland", "mixed",
           "Ask first in Ireland",
           "One-party rules apply to some calls, but GDPR treats voices as personal data. Ask everyone first."),
    "DE": ("Germany", "all_party",
           "Everyone must agree in Germany",
           "Recording private spoken words without consent is a criminal offence in Germany (§201 StGB)."),
    "FR": ("France", "all_party",
           "Everyone must agree in France",
           "Recording private conversations without consent can breach French privacy law."),
    "ES": ("Spain", "mixed",
           "Ask first in Spain",
           "Participants may record in some cases, but GDPR applies to storing voices. Ask everyone first."),
    "IT": ("Italy", "mixed",
           "Ask first in Italy",
           "Participants may record in some cases, but GDPR applies to storing voices. Ask everyone first."),
    "NL": ("Netherlands", "mixed",
           "Ask first in the Netherlands",
           "Participants may record their own conversations, but GDPR applies to storing voices."),
    "AU": ("Australia", "mixed",
           "Rules vary by state in Australia",
           "Several Australian states require everyone's consent. Ask everyone first."),
    "NZ": ("New Zealand", "one_party",
           "One-party consent in New Zealand",
           "You can generally record a conversation you take part in, but privacy principles still apply."),
    # Legal review pending (see docs/LAUNCH.md).
    "IN": ("India", "unknown",
           "Ask everyone first in India",
           "India has no single law on recording conversations you take part in, but the Constitution protects "
           "privacy and the Digital Personal Data Protection Act, 2023 covers storing and processing people's "
           "voices. Comlogue only works with recordings everyone has agreed to."),
    "SG": ("Singapore", "mixed",
           "Ask first in Singapore",
           "Personal data protection rules can apply to recordings. Ask everyone first."),
    "JP": ("Japan", "one_party",
           "Ask first in Japan",
           "Recording a conversation you take part in is generally allowed, but sharing it may not be."),
    "BR": ("Brazil", "mixed",
           "Ask first in Brazil",
           "Participants may record, but data-protection law (LGPD) applies to storing voices."),
    "MX": ("Mexico", "mixed",
           "Ask first in Mexico",
           "Participants may record in some cases; privacy law applies to sharing. Ask everyone first."),
}

EU_GDPR_NOTE = (
    "In the EU, data-protection law (GDPR) treats people's voices as personal data. Ask everyone first."
)


def _regions() -> list[CodeName]:
    regions = [CodeName(code=f"US-{code}", name=f"{name}, US") for code, name in sorted(US_STATES.items(),
                                                                                         key=lambda kv: kv[1])]
    regions += [CodeName(code=code, name=data[0]) for code, data in sorted(COUNTRIES.items(), key=lambda kv: kv[1][0])]
    regions.append(CodeName(code="OTHER", name="Somewhere else"))
    return regions


REGIONS = _regions()


def rules_for(region: str | None) -> RecordingRules:
    code = (region or "OTHER").strip().upper()
    if code.startswith("IN-"):
        code = "IN"  # Indian states share the national guidance
    if code.startswith("US-") and code[3:] in US_STATES:
        state = code[3:]
        name = US_STATES[state]
        if state in ALL_PARTY:
            rule, headline = "all_party", f"Everyone must agree in {name}"
            detail = (
                f"{name} is an all-party consent state: everyone in a private conversation must agree before "
                "it's recorded."
            )
        elif state in MIXED:
            rule, headline, detail = "mixed", f"It depends on the situation in {name}", MIXED[state]
        elif state in NO_STATUTE:
            rule, headline, detail = "unknown", f"Ask first in {name}", NO_STATUTE[state]
        else:
            rule, headline = "one_party", f"One-party consent in {name}"
            detail = (
                f"In {name} you can generally record a conversation you're part of. We still ask you to tell "
                "everyone — it's the respectful thing to do, and the recording may include them."
            )
        return RecordingRules(region=code, region_name=f"{name}, US", rule=rule, headline=headline, detail=detail,
                              policy=POLICY, how_to_ask=HOW_TO_ASK, disclaimer=DISCLAIMER, regions=REGIONS)
    if code == "US":
        return RecordingRules(
            region="US", region_name="United States", rule="mixed", headline="It depends on your state",
            detail="Some US states require everyone's consent, others only yours. Pick your state for details.",
            policy=POLICY, how_to_ask=HOW_TO_ASK, disclaimer=DISCLAIMER, regions=REGIONS)
    if code in COUNTRIES:
        name, rule, headline, detail = COUNTRIES[code]
        return RecordingRules(region=code, region_name=name, rule=rule, headline=headline, detail=detail,
                              policy=POLICY, how_to_ask=HOW_TO_ASK, disclaimer=DISCLAIMER, regions=REGIONS)
    if code in {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "GR", "HU", "LV", "LT", "LU", "MT", "PL",
                "PT", "RO", "SK", "SI", "SE"}:
        return RecordingRules(region=code, region_name="European Union", rule="mixed", headline="Ask first in the EU",
                              detail=EU_GDPR_NOTE, policy=POLICY, how_to_ask=HOW_TO_ASK, disclaimer=DISCLAIMER,
                              regions=REGIONS)
    return RecordingRules(
        region="OTHER", region_name="Your region", rule="unknown", headline="Ask everyone first",
        detail="Recording laws vary by country. Asking everyone before you record keeps you on safe ground.",
        policy=POLICY, how_to_ask=HOW_TO_ASK, disclaimer=DISCLAIMER, regions=REGIONS)
