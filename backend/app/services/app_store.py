"""Verify StoreKit 2 signed transactions (JWS) against Apple's root certificate.

A signed transaction is a compact JWS (ES256) whose `x5c` header carries the leaf and intermediate
certificates, then a root. We never trust the root the token carries: the intermediate must be issued by one of
our own trusted roots (Apple Root CA - G3, bundled in `app/certs/`), the leaf by the intermediate, each must be
valid now and carry Apple's marker extension, and the leaf's key must sign the token. This mirrors the checks in
Apple's `app-store-server-library` except the online OCSP revocation check.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import jwt
from cryptography import x509
from cryptography.exceptions import InvalidSignature

BUNDLED_ROOTS_DIR = Path(__file__).resolve().parent.parent / "certs"

# Marker extensions Apple puts on its App Store receipt-signing certificates.
APPLE_INTERMEDIATE_OID = x509.ObjectIdentifier("1.2.840.113635.100.6.2.1")
APPLE_LEAF_OID = x509.ObjectIdentifier("1.2.840.113635.100.6.11.1")


class VerificationError(Exception):
    """The signed transaction isn't from the App Store (or can't be checked)."""


def load_root_certificates(paths: Iterable[str]) -> list[x509.Certificate]:
    """Load DER or PEM certificates; with no paths, every certificate bundled in `app/certs/`."""
    files = [Path(path) for path in paths] or sorted(BUNDLED_ROOTS_DIR.glob("*.cer"))
    roots = []
    for file in files:
        data = file.read_bytes()
        roots.append(x509.load_pem_x509_certificate(data) if data.lstrip().startswith(b"-----")
                     else x509.load_der_x509_certificate(data))
    return roots


def _certificate(encoded: object) -> x509.Certificate:
    if not isinstance(encoded, str):
        raise VerificationError("x5c entries must be strings")
    try:
        return x509.load_der_x509_certificate(base64.b64decode(encoded, validate=True))
    except (binascii.Error, ValueError) as exc:
        raise VerificationError("x5c entry isn't a certificate") from exc


def _issued_by(certificate: x509.Certificate, issuer: x509.Certificate) -> bool:
    try:
        certificate.verify_directly_issued_by(issuer)
    except (ValueError, TypeError, InvalidSignature):
        return False
    return True


def _check_valid(certificate: x509.Certificate, now: datetime) -> None:
    if not certificate.not_valid_before_utc <= now <= certificate.not_valid_after_utc:
        raise VerificationError(f"certificate {certificate.subject.rfc4514_string()} isn't valid now")


def _has_extension(certificate: x509.Certificate, oid: x509.ObjectIdentifier) -> bool:
    try:
        certificate.extensions.get_extension_for_oid(oid)
    except x509.ExtensionNotFound:
        return False
    return True


def _is_ca(certificate: x509.Certificate) -> bool:
    try:
        return certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca
    except x509.ExtensionNotFound:
        return False


def verify_signed_payload(token: str, roots: list[x509.Certificate], now: datetime | None = None) -> dict:
    """Return the payload of an App Store-signed JWS, or raise `VerificationError`."""
    if not roots:
        raise VerificationError("no trusted root certificates are configured")
    now = now or datetime.now(UTC)
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise VerificationError("not a JWS") from exc
    if header.get("alg") != "ES256":
        raise VerificationError("unexpected signing algorithm")
    chain = header.get("x5c")
    if not isinstance(chain, list) or len(chain) < 2:
        raise VerificationError("missing certificate chain")
    leaf, intermediate = _certificate(chain[0]), _certificate(chain[1])

    root = next((candidate for candidate in roots if _issued_by(intermediate, candidate)), None)
    if root is None:
        raise VerificationError("chain doesn't lead to a trusted root")
    if not _is_ca(intermediate) or not _has_extension(intermediate, APPLE_INTERMEDIATE_OID):
        raise VerificationError("intermediate isn't an Apple App Store CA")
    if not _issued_by(leaf, intermediate):
        raise VerificationError("leaf isn't issued by the intermediate")
    if not _has_extension(leaf, APPLE_LEAF_OID):
        raise VerificationError("leaf isn't an App Store signing certificate")
    for certificate in (root, intermediate, leaf):
        _check_valid(certificate, now)

    try:
        payload = jwt.decode(token, key=leaf.public_key(), algorithms=["ES256"],
                             options={"verify_aud": False, "verify_iss": False})
    except jwt.PyJWTError as exc:
        raise VerificationError("signature doesn't match") from exc
    if not isinstance(payload, dict):
        raise VerificationError("payload isn't an object")
    return payload
