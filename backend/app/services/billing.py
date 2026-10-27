"""Entitlements from App Store purchases (StoreKit 2 signed transactions).

Where verification is required (production, unless APP_STORE_REQUIRE_VERIFICATION says otherwise), a
transaction counts only if its JWS signature chains to Apple's root certificate (`services/app_store.py`).
Elsewhere, transactions from Xcode's local StoreKit testing (signed by a local certificate) are decoded,
sanity-checked and recorded as unverified.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime
from functools import lru_cache

from cryptography import x509

from ..config import Settings
from ..errors import APIError, validation
from ..models import User
from ..schemas import Entitlement
from ..timeutil import iso
from . import app_store

log = logging.getLogger("comlogue.billing")


def _decode_payload(jws: str) -> dict:
    try:
        payload = jws.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError) as exc:
        raise validation("That purchase receipt couldn't be read.") from exc


@lru_cache
def _trusted_roots(paths: tuple[str, ...]) -> list[x509.Certificate]:
    return app_store.load_root_certificates(paths)


def apply_app_store_transaction(settings: Settings, user: User, signed_transaction: str) -> Entitlement:
    verified = settings.app_store_verification_required
    if verified:
        try:
            payload = app_store.verify_signed_payload(
                signed_transaction, _trusted_roots(tuple(settings.app_store_root_certificates)))
        except app_store.VerificationError as exc:
            log.warning("Rejected an App Store transaction for %s: %s", user.id, exc)
            raise validation("We couldn't verify this purchase with the App Store.") from exc
    else:
        payload = _decode_payload(signed_transaction)
    product_id = payload.get("productId")
    if product_id not in settings.app_store_product_ids:
        raise validation("Unknown product.")
    bundle_id = payload.get("bundleId")
    # A verified transaction must name this app; local StoreKit testing may leave the bundle id out.
    if settings.app_store_bundle_id and (verified or bundle_id) and bundle_id != settings.app_store_bundle_id:
        raise validation("This purchase belongs to a different app.")
    if payload.get("revocationDate"):
        raise validation("This purchase was refunded or revoked.")
    expires_ms = payload.get("expiresDate")
    if not expires_ms:
        # Every product is an auto-renewable subscription, so a transaction without an expiry isn't one of ours.
        raise validation("This purchase has no expiry date.")
    expires = datetime.fromtimestamp(int(expires_ms) / 1000, tz=UTC).replace(microsecond=0)
    if not verified:
        log.warning("Recording UNVERIFIED App Store transaction %s for %s (verification is off)",
                    payload.get("transactionId"), user.id)
    user.entitlement = {"tier": "pro", "expires_at": iso(expires), "source": "app_store", "product_id": product_id,
                        "verified": verified, "original_transaction_id": payload.get("originalTransactionId"),
                        "environment": payload.get("environment")}
    return Entitlement(tier="pro", expires_at=iso(expires), source="app_store", product_id=product_id)


def dev_grant(settings: Settings, user: User, tier: str) -> Entitlement:
    if not settings.dev_entitlements_allowed:
        raise APIError(403, "forbidden", "Developer entitlements are disabled on this server.")
    if tier == "pro":
        user.entitlement = {"tier": "pro", "expires_at": None, "source": "dev", "product_id": None}
        return Entitlement(tier="pro", expires_at=None, source="dev", product_id=None)
    user.entitlement = {"tier": "free", "expires_at": None, "source": "none", "product_id": None}
    return Entitlement(tier="free", expires_at=None, source="none", product_id=None)
