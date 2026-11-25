"""Standard HS256 JWT token creation and verification utilities for client authentication."""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

import backend.config as app_config


def _b64url_encode(data: bytes) -> str:
    """Return URL-safe base64 string without '=' padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    """Decode a URL-safe base64 segment, restoring required '=' padding."""
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode((segment + padding).encode("ascii"))


def _get_jwt_secret(secret_key: Optional[str] = None) -> str:
    """Resolve the active JWT secret key from argument, config, or environment."""
    if secret_key:
        return secret_key
    return (
        getattr(app_config, "JWT_SECRET_KEY", None)
        or os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-key")
    )


def create_jwt_token(
    client_id: int,
    secret_key: Optional[str] = None,
    expires_in_seconds: int = 86400,
) -> str:
    """Create an HS256-signed JWT token encoding the given client_id."""
    secret = _get_jwt_secret(secret_key)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(client_id),
        "client_id": client_id,
        "exp": int(time.time()) + expires_in_seconds,
    }
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_jwt_token(
    token: str,
    secret_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify and decode an HS256 JWT token, raising ValueError if invalid or expired."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Malformed JWT token: expected 3 dot-separated segments.")

    header_b64, payload_b64, signature_b64 = parts
    secret = _get_jwt_secret(secret_key)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    expected_sig_b64 = _b64url_encode(expected_sig)

    if not hmac.compare_digest(expected_sig_b64, signature_b64):
        raise ValueError("Invalid JWT signature.")

    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Malformed JWT payload.") from exc

    if not isinstance(payload, dict):
        raise ValueError("JWT payload must be a JSON object.")

    exp = payload.get("exp")
    if exp is not None and float(exp) < time.time():
        raise ValueError("JWT token has expired.")

    return payload


def extract_client_id_from_jwt(
    token: str,
    secret_key: Optional[str] = None,
) -> int:
    """Decode a verified JWT token and return the integer client_id (`Clients.id`)."""
    payload = decode_jwt_token(token, secret_key=secret_key)
    raw_id = payload.get("client_id") or payload.get("id") or payload.get("sub")
    if raw_id is None:
        raise ValueError("JWT token does not contain a client_id or sub claim.")
    try:
        return int(raw_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("JWT client_id claim must be an integer.") from exc
