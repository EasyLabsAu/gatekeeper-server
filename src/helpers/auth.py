import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Security
from fastapi.applications import FastAPI
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext

from core.config import settings
from helpers.utils import APIError

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 1
REFRESH_TOKEN_EXPIRE_HOURS = 24
REFRESH_TOKEN_MAX_DAYS = 7

security = HTTPBearer(auto_error=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
token_blacklist: set[str] = set()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    jti = str(uuid.uuid4())
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "access",
        "iat": now,
        "jti": jti,
    }
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)


def create_refresh_token(
    subject: str | Any,
    expires_delta: timedelta = timedelta(hours=REFRESH_TOKEN_EXPIRE_HOURS),
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    refresh_exp = now + timedelta(days=REFRESH_TOKEN_MAX_DAYS)
    jti = str(uuid.uuid4())

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": now,
        "type": "refresh",
        "jti": jti,
        "refresh_exp": refresh_exp.isoformat(),
    }
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)


def verify_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])

        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            raise ExpiredSignatureError("Access token has expired")

        return payload

    except ExpiredSignatureError:
        raise ValueError(401, "Access token has expired")
    except InvalidTokenError:
        raise ValueError(401, "Invalid or malformed access token")
    except Exception as e:
        raise ValueError(401, f"Token validation failed: {str(e)}")


def verify_refresh_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise APIError(401, "Invalid token type")

        jti = payload.get("jti")
        if not jti or jti in token_blacklist:
            raise APIError(401, "Refresh token is revoked or reused")

        refresh_exp = payload.get("refresh_exp")
        if refresh_exp and datetime.now(timezone.utc) > datetime.fromisoformat(
            refresh_exp
        ):
            raise APIError(401, "Refresh token expired (max lifetime)")

        return payload
    except InvalidTokenError:
        raise APIError(401, "Invalid or expired refresh token")


def rotate_refresh_token(old_token: str) -> tuple[str, str]:
    payload = verify_refresh_token(old_token)

    old_jti = payload.get("jti")
    if old_jti:
        token_blacklist.add(old_jti)

    new_access_token = create_access_token(payload["sub"])
    new_refresh_token = create_refresh_token(payload["sub"])

    return new_access_token, new_refresh_token


def get_public_paths(app: FastAPI) -> set[str]:
    public_paths = {
        "/docs",
        "/redoc",
        "/openapi.json",
        "/docs/oauth2-redirect",
    }
    for route in app.routes:
        if isinstance(route, APIRoute) and getattr(route.endpoint, "_is_public", False):
            public_paths.add(route.path)
    return public_paths


def public_route(route_handler):
    route_handler._is_public = True
    return route_handler


def require_auth(token: HTTPAuthorizationCredentials = Security(security)):
    if not token or not token.credentials:
        return APIError(401, "Missing Authorization token")

    raw_token = token.credentials

    if raw_token in token_blacklist:
        return APIError(401, "Token has been revoked or reused")

    try:
        return verify_access_token(raw_token)
    except Exception as e:
        return APIError(401, f"Unauthorized: {str(e)}")


def create_one_time_password() -> str:
    otp = secrets.randbelow(900000) + 100000
    return str(otp)
