"""Cognito JWT validation with JWKS key caching."""

import logging
import os

import jwt
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None
_JWKS_CACHE_LIFETIME = 3600  # seconds


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        region = os.environ.get("AWS_REGION", "us-east-1")
        pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
        if not pool_id:
            raise ValueError("COGNITO_USER_POOL_ID environment variable is required")
        url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
        _jwks_client = PyJWKClient(url, cache_keys=True, lifespan=_JWKS_CACHE_LIFETIME)
    return _jwks_client


def decode_and_verify(token: str) -> dict:
    """Decode and verify a Cognito JWT token.

    Validates: signature (RS256 via JWKS), expiration, issuer, and token_use.
    Returns the decoded claims dict, or raises on any failure.
    """
    region = os.environ.get("AWS_REGION", "us-east-1")
    pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"

    client = _get_jwks_client()
    signing_key = client.get_signing_key_from_jwt(token)

    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=issuer,
        options={"require": ["exp", "iss", "token_use"]},
    )
