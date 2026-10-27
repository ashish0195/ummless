"""Markets: the US and India get their own content, formats, defaults and pricing; everyone else is "global".

`market_for` derives the market from the onboarding region (`US-CA`, `IN`, `GB`…). Note `US-IN` is Indiana.
"""

from __future__ import annotations

MARKETS = ("us", "in", "global")

DEFAULT_TIMEZONE = {"us": "America/New_York", "in": "Asia/Kolkata", "global": "UTC"}


def market_for(region: str | None) -> str:
    code = (region or "").strip().upper()
    if code == "IN" or code.startswith("IN-"):
        return "in"
    if code == "US" or code.startswith("US-"):
        return "us"
    return "global"


def default_timezone(market: str) -> str:
    return DEFAULT_TIMEZONE.get(market, "UTC")


def relevance(markets: tuple[str, ...] | list[str], market: str) -> int:
    """Sort key for "market-relevant first": made for this market only (0), shared (1), elsewhere (2)."""
    if market in markets:
        return 0 if len(markets) == 1 else 1
    return 2
