"""Static product metadata the app needs (languages, goals, dimensions, consents, pricing)."""

from __future__ import annotations

from ..core import AppServices
from ..domain import consents
from ..domain.activities import ACTIVITIES, ACTIVITY_ORDER
from ..domain.course import TRACK_ORDER
from ..domain.dimensions import DIMENSIONS
from ..domain.languages import LANGUAGES
from ..schemas import (
    ActivityInfo,
    CodeName,
    DimensionInfo,
    IdTitle,
    Limits,
    Meta,
    Pricing,
)
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


def build(svc: AppServices) -> Meta:
    s = svc.settings
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
        pricing=Pricing(monthly_usd=s.price_monthly_usd, yearly_usd=s.price_yearly_usd, trial_days=s.trial_days,
                        monthly_product_id=s.monthly_product_id, yearly_product_id=s.yearly_product_id,
                        note="Introductory pricing for our pilot. You'll always see the price and terms before you buy."),
        consents=consents.ALL,
        limits=Limits(free_spar_per_week=s.free_spar_per_week, free_talks=s.free_talks, max_upload_mb=s.max_upload_mb,
                      max_recording_minutes=s.max_recording_minutes),
    )
