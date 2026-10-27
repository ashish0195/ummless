"""App Store signed-transaction verification, with a throwaway chain shaped like Apple's."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.services.app_store import (
    APPLE_INTERMEDIATE_OID,
    APPLE_LEAF_OID,
    VerificationError,
    load_root_certificates,
    verify_signed_payload,
)
from tests.helpers import signup

NOW = datetime(2026, 10, 27, tzinfo=UTC)
PAYLOAD = {"productId": "comlogue.pro.yearly", "bundleId": "com.comlogue.app", "transactionId": "2000000001",
           "originalTransactionId": "2000000001", "expiresDate": 4102444800000, "environment": "Sandbox",
           "type": "Auto-Renewable Subscription"}


def _cert(name: str, key, issuer_name: str, issuer_key, *, ca: bool, marker: x509.ObjectIdentifier | None,
          days: int = 365) -> x509.Certificate:
    builder = (x509.CertificateBuilder()
               .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
               .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer_name)]))
               .public_key(key.public_key())
               .serial_number(x509.random_serial_number())
               .not_valid_before(NOW - timedelta(days=1))
               .not_valid_after(NOW + timedelta(days=days))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if marker is not None:
        builder = builder.add_extension(x509.UnrecognizedExtension(marker, b"\x05\x00"), critical=False)
    return builder.sign(issuer_key, hashes.SHA384() if ca else hashes.SHA256())


class Chain:
    def __init__(self, *, intermediate_marker=APPLE_INTERMEDIATE_OID, leaf_marker=APPLE_LEAF_OID, leaf_days=365):
        self.root_key = ec.generate_private_key(ec.SECP384R1())
        self.root = _cert("Test Root CA", self.root_key, "Test Root CA", self.root_key, ca=True, marker=None)
        self.intermediate_key = ec.generate_private_key(ec.SECP384R1())
        self.intermediate = _cert("Test WWDR CA", self.intermediate_key, "Test Root CA", self.root_key, ca=True,
                                  marker=intermediate_marker)
        self.leaf_key = ec.generate_private_key(ec.SECP256R1())
        self.leaf = _cert("Test StoreKit signer", self.leaf_key, "Test WWDR CA", self.intermediate_key, ca=False,
                          marker=leaf_marker, days=leaf_days)

    def sign(self, payload: dict, *, key=None) -> str:
        x5c = [base64.b64encode(c.public_bytes(serialization.Encoding.DER)).decode()
               for c in (self.leaf, self.intermediate, self.root)]
        return jwt.encode(payload, key or self.leaf_key, algorithm="ES256", headers={"x5c": x5c})

    def root_pem(self, tmp_path) -> str:
        path = tmp_path / "root.pem"
        path.write_bytes(self.root.public_bytes(serialization.Encoding.PEM))
        return str(path)


def test_accepts_a_transaction_signed_through_a_trusted_chain() -> None:
    chain = Chain()
    assert verify_signed_payload(chain.sign(PAYLOAD), [chain.root], now=NOW) == PAYLOAD


def _unsigned(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"e30.{body}.sig"


@pytest.mark.parametrize("make_token", [
    pytest.param(lambda chain: _unsigned(PAYLOAD), id="unsigned"),
    pytest.param(lambda chain: Chain().sign(PAYLOAD), id="untrusted-root"),
    pytest.param(lambda chain: chain.sign(PAYLOAD, key=ec.generate_private_key(ec.SECP256R1())), id="wrong-key"),
    pytest.param(lambda chain: chain.sign(PAYLOAD)[:-8] + "AAAAAAAA", id="tampered-signature"),
    pytest.param(lambda chain: jwt.encode(PAYLOAD, "s" * 32, algorithm="HS256",
                                          headers={"x5c": jwt.get_unverified_header(chain.sign(PAYLOAD))["x5c"]}),
                 id="hmac-algorithm"),
])
def test_rejects_forged_transactions(make_token) -> None:
    chain = Chain()
    with pytest.raises(VerificationError):
        verify_signed_payload(make_token(chain), [chain.root], now=NOW)


def test_rejects_a_payload_swapped_under_a_valid_signature() -> None:
    chain = Chain()
    header, _, signature = chain.sign(PAYLOAD).split(".")
    forged = base64.urlsafe_b64encode(json.dumps({**PAYLOAD, "productId": "x"}).encode()).decode().rstrip("=")
    with pytest.raises(VerificationError):
        verify_signed_payload(f"{header}.{forged}.{signature}", [chain.root], now=NOW)


@pytest.mark.parametrize("chain_kwargs", [
    pytest.param({"intermediate_marker": None}, id="intermediate-without-apple-marker"),
    pytest.param({"leaf_marker": None}, id="leaf-without-apple-marker"),
])
def test_rejects_certificates_apple_did_not_mark(chain_kwargs) -> None:
    chain = Chain(**chain_kwargs)
    with pytest.raises(VerificationError):
        verify_signed_payload(chain.sign(PAYLOAD), [chain.root], now=NOW)


def test_rejects_an_expired_signing_certificate() -> None:
    chain = Chain(leaf_days=10)
    with pytest.raises(VerificationError, match="isn't valid now"):
        verify_signed_payload(chain.sign(PAYLOAD), [chain.root], now=NOW + timedelta(days=30))


def test_bundles_apples_root_certificate() -> None:
    (root,) = load_root_certificates([])
    assert root.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == "Apple Root CA - G3"
    assert root.fingerprint(hashes.SHA256()).hex() == (
        "63343abfb89a6a03ebb57e9b3f5fa7be7c4f5c756f3017b3a8c488c3653e9179")


@pytest.fixture
def chain() -> Chain:
    return Chain()


@pytest.fixture
def verifying_settings(settings, chain, tmp_path):
    settings.app_store_require_verification = True
    settings.app_store_root_certificates = [chain.root_pem(tmp_path)]
    return settings


def test_purchase_endpoint_grants_pro_only_for_verified_transactions(verifying_settings, client, chain) -> None:
    headers = signup(client)
    for token in (_unsigned(PAYLOAD), Chain().sign(PAYLOAD), chain.sign({**PAYLOAD, "bundleId": "com.other.app"}),
                  chain.sign({k: v for k, v in PAYLOAD.items() if k != "expiresDate"})):
        response = client.post("/v1/billing/app-store", json={"signed_transaction": token}, headers=headers)
        assert response.status_code == 422, token
    assert client.get("/v1/me", headers=headers).json()["entitlement"]["tier"] == "free"

    ent = client.post("/v1/billing/app-store", json={"signed_transaction": chain.sign(PAYLOAD)}, headers=headers)
    assert ent.status_code == 200
    assert ent.json()["tier"] == "pro" and ent.json()["expires_at"] == "2100-01-01T00:00:00Z"
    assert client.get("/v1/me", headers=headers).json()["entitlement"]["tier"] == "pro"
