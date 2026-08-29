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
