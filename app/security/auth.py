from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import get_user_repository
from app.config import Settings, get_settings
from app.db.user_repository import UserRepository

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(username: str, settings: Settings) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.auth_token_expiry_minutes),
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm="HS256")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    if not settings.auth_secret_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {
                "error": {
                    "code": "AUTH_NOT_CONFIGURED",
                    "message": "Authentication is not configured",
                    "details": {},
                }
            },
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            {"error": {"code": "UNAUTHORIZED", "message": "Missing bearer token", "details": {}}},
            {"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.auth_secret_key,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            {"error": {"code": "TOKEN_EXPIRED", "message": "Token has expired", "details": {}}},
            {"WWW-Authenticate": "Bearer"},
        ) from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            {"error": {"code": "INVALID_TOKEN", "message": "Invalid token", "details": {}}},
            {"WWW-Authenticate": "Bearer"},
        ) from error
    username = payload.get("sub")
    if not isinstance(username, str) or repository.get_by_username(username) is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            {"error": {"code": "UNKNOWN_USER", "message": "Unknown user", "details": {}}},
            {"WWW-Authenticate": "Bearer"},
        )
    return username
