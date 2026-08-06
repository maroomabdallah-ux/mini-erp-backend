# app/core/security.py

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)


def hash_password(password: str) -> str:
    return cast(str, password_context.hash(password))


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return cast(
        bool,
        password_context.verify(
            plain_password,
            hashed_password,
        ),
    )


def create_access_token(
    subject: str | int,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_minutes)

    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }

    if additional_claims:
        payload.update(additional_claims)

    return cast(
        str,
        jwt.encode(
            payload,
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        ),
    )


def create_refresh_token(
    subject: str | int,
    token_id: str | None = None,
) -> tuple[str, str, datetime]:
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_days)

    token_id = token_id or secrets.token_urlsafe(32)

    payload = {
        "sub": str(subject),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": token_id,
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, token_id, expire


def hash_token_id(token_id: str) -> str:
    return hashlib.sha256(token_id.encode("utf-8")).hexdigest()


def decode_token(token: str) -> dict[str, Any]:
    try:
        return cast(
            dict[str, Any],
            jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=[settings.jwt_algorithm],
            ),
        )

    except JWTError as exc:
        raise ValueError("Invalid or expired token.") from exc
