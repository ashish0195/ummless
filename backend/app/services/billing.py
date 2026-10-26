"""Entitlements from App Store purchases (StoreKit 2 signed transactions).

TODO(launch): verify the JWS signature chain against Apple's root certificates (Apple's
`app-store-server-library`) or call the App Store Server API before trusting a transaction. Until then,
transactions are decoded and sanity-checked (bundle id, product id, expiry) and recorded as unverified;
set APP_STORE_REQUIRE_VERIFICATION=true to refuse unverified purchases.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime

from ..config import Settings
from ..errors import APIError, validation
from ..models import User
from ..schemas import Entitlement
from ..timeutil import iso

log = logging.getLogger("comlogue.billing")


def _decode_payload(jws: str) -> dict:
    try:
        payload = jws.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError) as exc:
        raise validation("That purchase receipt couldn't be read.") from exc


def apply_app_store_transaction(settings: Settings, user: User, signed_transaction: str) -> Entitlement:
    if settings.app_store_require_verification:
        raise APIError(501, "not_implemented", "Purchase verification isn't configured on this server yet.")
    payload = _decode_payload(signed_transaction)
    product_id = payload.get("productId")
    if product_id not in settings.app_store_product_ids:
        raise validation("Unknown product.")
    bundle_id = payload.get("bundleId")
    if settings.app_store_bundle_id and bundle_id and bundle_id != settings.app_store_bundle_id:
        raise validation("This purchase belongs to a different app.")
    if payload.get("revocationDate"):
        raise validation("This purchase was refunded or revoked.")
    expires_ms = payload.get("expiresDate")
    expires = (datetime.fromtimestamp(int(expires_ms) / 1000, tz=UTC).replace(microsecond=0)
               if expires_ms else None)
    log.warning("Recording UNVERIFIED App Store transaction %s for %s (TODO: verify JWS)",
                payload.get("transactionId"), user.id)
    user.entitlement = {"tier": "pro", "expires_at": iso(expires), "source": "app_store", "product_id": product_id,
                        "verified": False, "original_transaction_id": payload.get("originalTransactionId"),
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
