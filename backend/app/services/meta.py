"""Static product metadata the app needs (languages, goals, dimensions, consents, pricing)."""

from __future__ import annotations

from ..config import Settings
from ..core import AppServices
from ..domain import consents
from ..domain.activities import ACTIVITIES, ACTIVITY_ORDER
from ..domain.content.consent_translations import CONSENT_TRANSLATIONS
from ..domain.course import TRACK_ORDER
from ..domain.dimensions import DIMENSIONS
from ..domain.languages import LANGUAGES
from ..domain.market_content import event_kinds
from ..domain.markets import MARKETS
from ..models import User
from ..schemas import (
    ActivityInfo,
    CodeName,
    Consents,
    ConsentText,
    ConsentTranslation,
    DimensionInfo,
    EventKindInfo,
    IdTitle,
    Limits,
    Meta,
    Pricing,
    SupportInfo,
)
from . import users
from .course import track_info

CONTEXTS = [
    IdTitle(id="social", title="Friends & social situations"),
    IdTitle(id="networking", title="Networking"),
    IdTitle(id="meetings", title="Meetings"),
    IdTitle(id="interviews", title="Interviews"),
]
EASE_TARGETS = [
    IdTitle(id="explaining", title="Explaining myself"),
    IdTitle(id="contributing", title="Contributing"),
    IdTitle(id="connecting", title="Connecting"),
    IdTitle(id="persuading", title="Persuading"),
    IdTitle(id="concise", title="Being concise"),
]


PRICING_NOTE = "Introductory pricing for our pilot. You'll always see the price and terms before you buy."


def _group_indian(whole: int) -> str:
    """12345678 → '1,23,45,678' (lakh/crore grouping)."""
    digits = str(whole)
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def money(amount: float, currency: str) -> str:
    """'$14.99' or '₹399' / '₹2,499' / '₹1,24,999.50' (Indian digit grouping, paise only when present)."""
    if currency != "INR":
        return f"${amount:,.2f}"
    paise = int(round(amount * 100))
    rupees, fraction = divmod(paise, 100)
    return f"₹{_group_indian(rupees)}" + (f".{fraction:02d}" if fraction else "")


def pricing(settings: Settings, market: str) -> Pricing:
    if market == "in":
        currency, monthly, yearly = "INR", settings.price_monthly_inr, settings.price_yearly_inr
    else:
        currency, monthly, yearly = "USD", settings.price_monthly_usd, settings.price_yearly_usd
    return Pricing(monthly_usd=settings.price_monthly_usd, yearly_usd=settings.price_yearly_usd,
                   trial_days=settings.trial_days, monthly_product_id=settings.monthly_product_id,
                   yearly_product_id=settings.yearly_product_id, note=PRICING_NOTE, currency=currency,
                   monthly_price=monthly, yearly_price=yearly, monthly_display=money(monthly, currency),
                   yearly_display=money(yearly, currency))


def _with_translations(kind: str, text: ConsentText) -> ConsentText:
    translations = {
        language: ConsentTranslation(title=items[kind]["title"], body=items[kind]["body"],
                                     bullets=list(items[kind]["bullets"]))
        for language, items in CONSENT_TRANSLATIONS.items() if kind in items
    }
    return text.model_copy(update={"translations": translations})


def consent_texts() -> Consents:
    return Consents(analysis=_with_translations("analysis", consents.ANALYSIS),
                    voice_reference=_with_translations("voice_reference", consents.VOICE_REFERENCE),
                    recording=_with_translations("recording", consents.RECORDING))


def build(svc: AppServices, user: User | None = None) -> Meta:
    s = svc.settings
    market = users.market(user) if user is not None else "us"
    return Meta(
        demo_mode=svc.demo_mode,
        api_version="1",
        languages=[CodeName(code=code, name=name) for code, name in LANGUAGES],
        tracks=[track_info(track_id) for track_id in TRACK_ORDER],
        contexts=CONTEXTS,
        ease_targets=EASE_TARGETS,
        dimensions=[DimensionInfo(id=d.id, title=d.title, description=d.description, symbol=d.symbol,
                                  color_hex=d.color_hex) for d in DIMENSIONS.values()],
        activities=[ActivityInfo(id=a.id, title=a.title, prompt=a.prompt, duration_label=a.duration_label,
                                 suggested_seconds=a.suggested_seconds, dimensions=list(a.dimensions))
                    for a in (ACTIVITIES[i] for i in ACTIVITY_ORDER)],
        assessment_estimate_minutes=[10, 15],
        voice_setup_estimate_minutes=1,
        pricing=pricing(s, market),
        pricing_by_market={m: pricing(s, m) for m in MARKETS},
        consents=consent_texts(),
        limits=Limits(free_spar_per_week=s.free_spar_per_week, free_talks=s.free_talks, max_upload_mb=s.max_upload_mb,
                      max_recording_minutes=s.max_recording_minutes),
        event_kinds=[EventKindInfo(id=k.id, title=k.title, symbol=k.symbol, markets=list(k.markets))
                     for k in event_kinds()],
        support=SupportInfo(email=s.support_email, grievance_email=s.grievance_email,
                            grievance_officer=s.grievance_officer),
    )
