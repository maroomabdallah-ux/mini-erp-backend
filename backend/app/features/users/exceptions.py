# app/features/users/exceptions.py


from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError


class UserError(BusinessRuleError):
    """Base exception for the users feature."""


class UserNotFoundError(NotFoundError):
    def __init__(self, user_id: int):
        super().__init__(f"User with id {user_id} was not found.")


class EmailAlreadyExistsError(ConflictError):
    def __init__(self, email: str):
        super().__init__(f"A user with email '{email}' already exists.")


class WeakPasswordError(UserError):
    def __init__(self):
        super().__init__(
            "Password must be at least 8 characters long "
            "and contain uppercase, lowercase, and numeric characters."
        )


class UserAlreadyInactiveError(UserError):
    def __init__(self, user_id: int):
        super().__init__(f"User with id {user_id} is already inactive.")


class UsernameAlreadyExistsError(ConflictError):
    def __init__(self, username: str):
        super().__init__(f"A user with username '{username}' already exists.")
