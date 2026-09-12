import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import app_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(subject: Any) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        seconds=app_settings.ACCESS_TOKEN_EXPIRES
    )

    return jwt.encode(
        {"sub": str(subject), "exp": expire},
        app_settings.SECRET_KEY,
        algorithm=app_settings.ALGORITHM,
    )


def decode_access_token(token: str) -> str:
    """Returns the subject (admin ID as string). Raises jwt.InvalidTokenError on failure."""
    payload = jwt.decode(
        token,
        app_settings.SECRET_KEY,
        algorithms=[app_settings.ALGORITHM],
    )

    return str(payload["sub"])


def create_refresh_token() -> str:
    """A high-entropy opaque token — unlike the access token, it's not a JWT,
    just a random secret whose (hashed) value is looked up in the DB so it
    can be individually revoked/rotated."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """SHA-256 hex digest, used both to store a refresh token and to look it
    up again — the raw token itself is never persisted."""
    return hashlib.sha256(token.encode()).hexdigest()
