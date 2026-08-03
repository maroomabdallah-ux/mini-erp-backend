from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token_id,
    verify_password,
)
from app.features.audit.service import add_audit_log
from app.features.users import repository
from app.features.users.model import RefreshToken, User

_failed_logins: dict[str, deque[datetime]] = defaultdict(deque)


def _check_rate_limit(ip_address: str) -> None:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=settings.login_window_minutes)
    attempts = _failed_logins[ip_address]
    while attempts and attempts[0] < cutoff:
        attempts.popleft()
    if len(attempts) >= settings.login_max_attempts:
        raise UnauthorizedError("Too many failed login attempts. Try again later.")


def _record_failure(ip_address: str) -> None:
    _failed_logins[ip_address].append(datetime.now(UTC))


def _issue_tokens(db: Session, user: User) -> tuple[str, str]:
    access_token = create_access_token(user.id)
    refresh_token, token_id, expires_at = create_refresh_token(user.id)
    repository.add_refresh_token(
        db,
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token_id(token_id),
            expires_at=expires_at,
        ),
    )
    return access_token, refresh_token


def login(
    db: Session, login_value: str, password: str, ip_address: str
) -> tuple[str, str, User]:
    _check_rate_limit(ip_address)
    user = repository.get_user_by_login(db, login_value)
    if user is None or not verify_password(password, user.hashed_password):
        _record_failure(ip_address)
        raise UnauthorizedError("Invalid username/email or password.")
    if not user.is_active:
        raise ForbiddenError("This account is deactivated.")
    _failed_logins.pop(ip_address, None)
    access_token, refresh_token = _issue_tokens(db, user)
    add_audit_log(
        db,
        user_id=user.id,
        action="login",
        table_name="users",
        record_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    return access_token, refresh_token, user


def refresh(db: Session, raw_token: str) -> str:
    try:
        payload = decode_token(raw_token)
    except ValueError as exc:
        raise UnauthorizedError("Invalid or expired refresh token.") from exc
    if payload.get("type") != "refresh" or not payload.get("jti"):
        raise UnauthorizedError("Invalid refresh token type.")
    stored = repository.get_refresh_token(db, hash_token_id(payload["jti"]))
    now = datetime.now(UTC)
    if (
        stored is None
        or stored.revoked_at is not None
        or stored.expires_at <= now
        or not stored.user.is_active
    ):
        raise UnauthorizedError("Refresh token is invalid or revoked.")
    return create_access_token(stored.user_id)


def logout(db: Session, raw_token: str) -> None:
    try:
        payload = decode_token(raw_token)
    except ValueError as exc:
        raise UnauthorizedError("Invalid or expired refresh token.") from exc
    if payload.get("type") != "refresh" or not payload.get("jti"):
        raise UnauthorizedError("Invalid refresh token type.")
    stored = repository.get_refresh_token(db, hash_token_id(payload["jti"]))
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        db.commit()


def permission_codes(user: User) -> list[str]:
    return sorted(
        {
            permission.code
            for role in user.roles
            if role.is_active
            for permission in role.permissions
        }
    )
