from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings

ENTRA_STATE_COOKIE_NAME = "sparc_entra_state"
ENTRA_SCOPES = "openid profile email"
ENTRA_STATE_TTL_SECONDS = 600


@dataclass(frozen=True)
class EntraIdentity:
    tenant_id: str
    object_id: str
    email: str | None
    display_name: str | None


def entra_is_configured(settings: Settings | None = None) -> bool:
    active_settings = settings or get_settings()
    return bool(
        active_settings.auth_enabled
        and active_settings.entra_enabled
        and active_settings.entra_tenant_id
        and active_settings.entra_client_id
        and active_settings.entra_client_secret
        and active_settings.entra_redirect_uri
        and active_settings.auth_session_secret
    )


def entra_authorization_url(state: str, settings: Settings | None = None) -> str:
    active_settings = _require_entra_config(settings)
    params = {
        "client_id": active_settings.entra_client_id or "",
        "response_type": "code",
        "redirect_uri": active_settings.entra_redirect_uri or "",
        "response_mode": "query",
        "scope": ENTRA_SCOPES,
        "state": state,
    }
    return f"{_authority_base(active_settings)}/oauth2/v2.0/authorize?{urlencode(params)}"


def create_entra_state(settings: Settings | None = None) -> str:
    active_settings = _require_entra_config(settings)
    now = int(time.time())
    payload = {
        "nonce": secrets.token_urlsafe(24),
        "iat": now,
        "exp": now + ENTRA_STATE_TTL_SECONDS,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body, active_settings)}"


def verify_entra_state(state: str, settings: Settings | None = None) -> bool:
    active_settings = _require_entra_config(settings)
    try:
        body, signature = state.split(".", 1)
    except ValueError:
        return False
    if not hmac.compare_digest(signature, _sign(body, active_settings)):
        return False
    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return False
    return int(payload.get("exp", 0)) >= int(time.time())


def exchange_code_for_identity(code: str, settings: Settings | None = None) -> EntraIdentity:
    active_settings = _require_entra_config(settings)
    tokens = _exchange_code_for_tokens(code, active_settings)
    id_token = tokens.get("id_token")
    if not isinstance(id_token, str) or not id_token:
        raise ValueError("Entra token response did not include an ID token")
    claims = validate_id_token(id_token, active_settings)
    tenant_id = str(claims.get("tid") or "").strip()
    object_id = str(claims.get("oid") or "").strip()
    if not tenant_id or not object_id:
        raise ValueError("Entra ID token did not include tenant and object identifiers")
    return EntraIdentity(
        tenant_id=tenant_id,
        object_id=object_id,
        email=_claim_email(claims),
        display_name=str(claims.get("name") or "").strip() or None,
    )


def validate_id_token(id_token: str, settings: Settings | None = None) -> dict[str, object]:
    active_settings = _require_entra_config(settings)
    import jwt
    from jwt import PyJWKClient

    jwks_client = PyJWKClient(f"{_authority_base(active_settings)}/discovery/v2.0/keys")
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=active_settings.entra_client_id,
        issuer=f"{_authority_base(active_settings)}/v2.0",
    )
    return claims if isinstance(claims, dict) else {}


def _exchange_code_for_tokens(code: str, settings: Settings) -> dict[str, object]:
    response = httpx.post(
        f"{_authority_base(settings)}/oauth2/v2.0/token",
        data={
            "client_id": settings.entra_client_id or "",
            "client_secret": settings.entra_client_secret or "",
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.entra_redirect_uri or "",
            "scope": ENTRA_SCOPES,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if response.status_code >= 400:
        raise ValueError("Entra authorization code exchange failed")
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def _require_entra_config(settings: Settings | None = None) -> Settings:
    active_settings = settings or get_settings()
    if not entra_is_configured(active_settings):
        raise ValueError("Entra authentication is not configured")
    return active_settings


def _authority_base(settings: Settings) -> str:
    authority = (settings.entra_authority_url or f"https://login.microsoftonline.com/{settings.entra_tenant_id}").strip().rstrip("/")
    if authority.endswith("/v2.0"):
        authority = authority.removesuffix("/v2.0")
    return authority


def _claim_email(claims: dict[str, object]) -> str | None:
    for key in ("preferred_username", "email", "upn"):
        value = str(claims.get(key) or "").strip().lower()
        if "@" in value:
            return value
    return None


def _sign(body: str, settings: Settings) -> str:
    secret = settings.auth_session_secret or ""
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
