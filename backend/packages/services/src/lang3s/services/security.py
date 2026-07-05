import enum
from dataclasses import dataclass, field
from typing import Annotated

import jwt
import requests
from cachetools import TTLCache, cached
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lang3s.core import config
from lang3s.services.permissions import PermissionAction, PermissionCategory

jwks_client = jwt.PyJWKClient(
    config.JWKS_URL,
    cache_keys=True,
    cache_jwk_set=True,
    lifespan=3600,
)


@dataclass(frozen=True)
class AuthedUser:
    user_id: str
    role: str
    permissions: dict[str, list[str]] = field(default_factory=dict)

    def has_permission(self, *action: PermissionAction) -> bool:
        for a in action:
            if a.value not in self.permissions.get(a.category, []):
                return False
        return True


class AuthTokenError(Exception):
    pass


SYSTEM_USER = AuthedUser(user_id="SYSTEM", role=config.SYSTEM_KEY)


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
                return AuthedUser(
                    user_id=payload.get("id"),
                    role=payload.get("role"),
                    permissions=payload.get("permissions"),
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
) -> AuthedUser:
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
    claims: Annotated[AuthedUser, Depends(require_auth)],
) -> AuthedUser:
    return claims


type AuthenticatedUserDep = Annotated[AuthedUser, Depends(get_authenticated_claim)]


def verify_jwks_token(token: str) -> AuthedUser:
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
        user_id = payload.get("id")
        if not user_id:
            raise AuthTokenError("Missing token subject")

        return AuthedUser(
            user_id=str(user_id),
            role=payload.get("role"),
            permissions=payload.get("permissions"),
        )
    except jwt.PyJWTError as exc:
        raise AuthTokenError("Invalid token") from exc
