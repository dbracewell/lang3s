from dataclasses import dataclass
from typing import Annotated

import jwt
import requests
from cachetools import TTLCache, cached
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lang3s.core import config

jwks_client = jwt.PyJWKClient(
    config.JWKS_URL,
    cache_keys=True,
    cache_jwk_set=True,
    lifespan=3600,
)


class AuthTokenError(Exception):
    pass


@dataclass(frozen=True)
class AuthClaims:
    sub: str
    role: str
    email: str | None = None
    name: str | None = None


@cached(TTLCache(maxsize=1024, ttl=3600))
def _check_api_key(api_key: str):
    try:
        r = requests.get(
            f"{config.BETTER_AUTH_URL}/api/verify",
            headers={"lang3s-api-key": api_key},
        )
        if r.ok:
            payload = r.json()
            if payload.get("valid", False):
                return AuthClaims(
                    sub=payload.get("user"),
                    role=payload.get("role"),
                )
        return None
    except Exception:
        return None


security = HTTPBearer(auto_error=False)


def require_auth(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(security),
    ],
) -> AuthClaims:
    if not credentials:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if str(credentials.credentials).startswith("lang3s-api-key-"):
        claim = _check_api_key(credentials.credentials)  # type: ignore
        if claim:
            return claim

    try:
        return verify_jwks_token(credentials.credentials)  # type: ignore
    except AuthTokenError as exc:
        raise HTTPException(status_code=401, detail="Unauthorized") from exc  # noqa: F821


def get_authenticated_claim(
    claims: Annotated[AuthClaims, Depends(require_auth)],
) -> AuthClaims:
    return claims


type AuthenticatedUserId = Annotated[AuthClaims, Depends(get_authenticated_claim)]


def verify_jwks_token(token: str) -> AuthClaims:
    """Verifies a Better Auth JWT using the JWKS endpoint and
    returns normalized auth claims."""
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config.JWT_AUDIENCE,
            issuer=config.JWT_ISSUER,
        )
        user_id = payload.get("sub")
        if not user_id:
            raise AuthTokenError("Missing token subject")

        return AuthClaims(
            sub=str(user_id),
            email=payload.get("email"),
            name=payload.get("name"),
            role=payload.get("role"),
        )
    except jwt.PyJWTError as exc:
        raise AuthTokenError("Invalid token") from exc
