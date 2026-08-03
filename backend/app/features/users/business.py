# app/features/users/business.py

import re

from app.core.exceptions import BusinessRuleError
from app.features.users.exceptions import (
    EmailAlreadyExistsError,
    UserAlreadyInactiveError,
    UsernameAlreadyExistsError,
    WeakPasswordError,
)
from app.features.users.model import User


def ensure_email_is_available(
    existing_user: User | None,
    email: str,
) -> None:
    """
    Business rule:
    Two users cannot use the same email address.
    """

    if existing_user is not None:
        raise EmailAlreadyExistsError(email)


def ensure_username_is_available(existing_user: User | None, username: str) -> None:
    if existing_user is not None:
        raise UsernameAlreadyExistsError(username)


def validate_password(password: str) -> None:
    """
    Business rules for a valid password:
    - At least 8 characters
    - Contains an uppercase letter
    - Contains a lowercase letter
    - Contains a number
    """

    has_minimum_length = len(password) >= 8
    has_uppercase = bool(re.search(r"[A-Z]", password))
    has_lowercase = bool(re.search(r"[a-z]", password))
    has_number = bool(re.search(r"\d", password))

    if not all(
        [
            has_minimum_length,
            has_uppercase,
            has_lowercase,
            has_number,
        ]
    ):
        raise WeakPasswordError()


def ensure_user_can_be_deactivated(user: User, *, actor_id: int) -> None:
    """
    Business rule:
    An already inactive user cannot be deactivated again.
    """

    if not user.is_active:
        raise UserAlreadyInactiveError(user.id)
    if user.id == actor_id:
        raise BusinessRuleError("You cannot deactivate your own account.")
