import importlib
import sys

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from lang3s.services.permissions import PermissionAction


def load_security_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SYSTEM_KEY", "test-system-key")
    sys.modules.pop("lang3s.services.security", None)
    return importlib.import_module("lang3s.services.security")


def test_authed_user_has_permission(monkeypatch: pytest.MonkeyPatch):
    security = load_security_module(monkeypatch)
    user = security.AuthedUser(
        user_id="u1",
        role="admin",
        permissions={"project": ["create", "delete"]},
    )

    assert user.has_permission(PermissionAction("project", "create"))
    assert not user.has_permission(PermissionAction("project", "update"))


def test_require_auth_rejects_missing_credentials(monkeypatch: pytest.MonkeyPatch):
    security = load_security_module(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        security.require_auth(None)

    assert exc.value.status_code == 401


def test_require_auth_accepts_valid_api_key(monkeypatch: pytest.MonkeyPatch):
    security = load_security_module(monkeypatch)
    expected_user = security.AuthedUser(user_id="u1", role="member", permissions={})

    monkeypatch.setattr(security, "_check_api_key", lambda _k: expected_user)

    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="lang3s-api-key-abc",
    )
    result = security.require_auth(creds)

    assert result == expected_user


def test_require_auth_falls_back_to_jwt(monkeypatch: pytest.MonkeyPatch):
    security = load_security_module(monkeypatch)
    expected_user = security.AuthedUser(user_id="jwt-user", role="member", permissions={})

    monkeypatch.setattr(security, "_check_api_key", lambda _k: None)
    monkeypatch.setattr(security, "verify_jwks_token", lambda _t: expected_user)

    creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="lang3s-api-key-invalid",
    )

    result = security.require_auth(creds)
    assert result == expected_user


def test_require_auth_invalid_jwt_returns_unauthorized(monkeypatch: pytest.MonkeyPatch):
    security = load_security_module(monkeypatch)

    def _raise(_token: str):
        raise security.AuthTokenError("invalid")

    monkeypatch.setattr(security, "verify_jwks_token", _raise)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="jwt-token")

    with pytest.raises(HTTPException) as exc:
        security.require_auth(creds)

    assert exc.value.status_code == 401
