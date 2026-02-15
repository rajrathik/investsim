"""Auth0 JWT verification for FastAPI.

Provides a `get_current_user` dependency that extracts and verifies
the Bearer token from the Authorization header against Auth0's JWKS.
"""

import json
import logging
import urllib.request
from functools import lru_cache

from fastapi import Depends, HTTPException, Request
from jose import jwt, JWTError

from app.config import AUTH0_DOMAIN, AUTH0_AUDIENCE, AUTH0_ALGORITHMS

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Raised when JWT verification fails."""
    def __init__(self, detail: str, status_code: int = 401):
        self.detail = detail
        self.status_code = status_code


@lru_cache(maxsize=1)
def get_jwks() -> dict:
    """Fetch and cache Auth0's JWKS (JSON Web Key Set).

    Cached for the lifetime of the process. If Auth0 rotates keys,
    restart the server or call get_jwks.cache_clear().
    """
    jwks_url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    logger.info("Fetching JWKS from %s", jwks_url)
    with urllib.request.urlopen(jwks_url, timeout=10) as response:
        return json.loads(response.read())


def get_token_from_header(request: Request) -> str:
    """Extract Bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise AuthError("Missing or invalid Authorization header")
    return auth[7:]


def verify_token(token: str) -> dict:
    """Verify a JWT token against Auth0's JWKS.

    Returns the decoded token payload containing 'sub', 'email', etc.
    """
    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)
    except AuthError:
        raise
    except Exception as e:
        raise AuthError(f"Token header error: {e}")

    # Find the matching RSA key
    rsa_key = {}
    for key in jwks.get("keys", []):
        if key["kid"] == unverified_header.get("kid"):
            rsa_key = {k: key[k] for k in ("kty", "kid", "use", "n", "e")}
            break

    if not rsa_key:
        # Key not found — might be rotated. Clear cache and retry once.
        get_jwks.cache_clear()
        try:
            jwks = get_jwks()
            for key in jwks.get("keys", []):
                if key["kid"] == unverified_header.get("kid"):
                    rsa_key = {k: key[k] for k in ("kty", "kid", "use", "n", "e")}
                    break
        except Exception:
            pass
        if not rsa_key:
            raise AuthError("Unable to find matching key in JWKS")

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=AUTH0_ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired")
    except jwt.JWTClaimsError:
        raise AuthError("Invalid token claims")
    except JWTError as e:
        raise AuthError(f"Token validation failed: {e}")


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and verify JWT, return user payload.

    Usage in route handlers:
        user: dict = Depends(get_current_user)

    The returned dict contains Auth0 token claims:
        - 'sub': stable user ID (e.g. 'auth0|abc123')
        - 'email': user's email (if scope includes 'email')
        - 'name': display name (if scope includes 'profile')
    """
    try:
        token = get_token_from_header(request)
        return verify_token(token)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
