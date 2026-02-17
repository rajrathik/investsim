"""Auth0 JWT verification for FastAPI.

Provides a `get_current_user` dependency that extracts and verifies
the Bearer token from the Authorization header.

Two modes:
  - If AUTH0_AUDIENCE is set: verifies JWT locally via JWKS (fast)
  - If AUTH0_AUDIENCE is empty: validates via Auth0 /userinfo endpoint
    (Auth0 returns opaque tokens when no audience is specified)
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
    """Fetch and cache Auth0's JWKS (JSON Web Key Set)."""
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


def verify_token_jwt(token: str) -> dict:
    """Verify a JWT token against Auth0's JWKS (when audience is set)."""
    try:
        jwks = get_jwks()
        unverified_header = jwt.get_unverified_header(token)
    except AuthError:
        raise
    except Exception as e:
        raise AuthError(f"Token header error: {e}")

    rsa_key = {}
    for key in jwks.get("keys", []):
        if key["kid"] == unverified_header.get("kid"):
            rsa_key = {k: key[k] for k in ("kty", "kid", "use", "n", "e")}
            break

    if not rsa_key:
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


def verify_token_userinfo(token: str) -> dict:
    """Verify an opaque token by calling Auth0's /userinfo endpoint.

    Used when no audience is configured (Auth0 issues opaque tokens).
    """
    userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
    req = urllib.request.Request(
        userinfo_url,
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            return data  # contains 'sub', 'email', 'name', etc.
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise AuthError("Token is invalid or expired")
        raise AuthError(f"Auth0 userinfo error: {e.code}")
    except Exception as e:
        raise AuthError(f"Failed to verify token: {e}")


def verify_token(token: str) -> dict:
    """Verify token using the appropriate method."""
    if AUTH0_AUDIENCE:
        return verify_token_jwt(token)
    else:
        return verify_token_userinfo(token)


def get_current_user(request: Request) -> dict:
    """FastAPI dependency: extract and verify token, return user payload.

    Usage in route handlers:
        user: dict = Depends(get_current_user)

    The returned dict contains Auth0 claims:
        - 'sub': stable user ID (e.g. 'auth0|abc123')
        - 'email': user's email (if scope includes 'email')
        - 'name': display name (if scope includes 'profile')
    """
    try:
        token = get_token_from_header(request)
        return verify_token(token)
    except AuthError as e:
        ip = request.client.host if request.client else "unknown"
        logger.warning(
            f"Auth failure: {e.detail} | IP={ip} | "
            f"Path={request.method} {request.url.path}"
        )
        raise HTTPException(status_code=e.status_code, detail=e.detail)
