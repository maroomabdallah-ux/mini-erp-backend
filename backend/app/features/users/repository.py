from typing import cast

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.features.users.model import Permission, RefreshToken, Role, User


def get_all_users(
    db: Session, *, offset: int = 0, limit: int = 20, search: str | None = None
) -> list[User]:
    statement = (
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(User.username).like(term),
                func.lower(User.email).like(term),
                func.lower(User.first_name).like(term),
                func.lower(User.last_name).like(term),
                func.lower(User.first_name + " " + User.last_name).like(term),
            )
        )
    statement = statement.order_by(User.id).offset(offset).limit(limit)
    return list(db.scalars(statement).unique().all())


def count_users(db: Session, *, search: str | None = None) -> int:
    statement = select(func.count(User.id))
    if search:
        term = f"%{search.strip().lower()}%"
        statement = statement.where(
            or_(
                func.lower(User.username).like(term),
                func.lower(User.email).like(term),
                func.lower(User.first_name).like(term),
                func.lower(User.last_name).like(term),
                func.lower(User.first_name + " " + User.last_name).like(term),
            )
        )
    return int(db.scalar(statement) or 0)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    statement = (
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    return cast(User | None, db.scalar(statement))


def get_user_by_email(db: Session, email: str) -> User | None:
    return cast(User | None, db.scalar(select(User).where(User.email == email.lower())))


def get_user_by_username(db: Session, username: str) -> User | None:
    return cast(
        User | None,
        db.scalar(select(User).where(User.username == username.lower())),
    )


def get_user_by_login(db: Session, login: str) -> User | None:
    normalized = login.lower()
    statement = (
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(or_(User.email == normalized, User.username == normalized))
    )
    return cast(User | None, db.scalar(statement))


def add_user(db: Session, user: User) -> User:
    db.add(user)
    return user


def save_user(db: Session, user: User) -> User:
    db.add(user)
    return user


def get_roles_by_ids(db: Session, role_ids: list[int]) -> list[Role]:
    if not role_ids:
        return []
    return list(db.scalars(select(Role).where(Role.id.in_(role_ids))).all())


def count_users_for_role(db: Session, role_id: int) -> int:
    role = get_role_by_id(db, role_id)
    return len(role.users) if role else 0


def get_all_roles(db: Session) -> list[Role]:
    return list(db.scalars(select(Role).order_by(Role.id)).all())


def get_role_by_id(db: Session, role_id: int) -> Role | None:
    return cast(
        Role | None,
        db.scalar(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.id == role_id)
        ),
    )


def get_role_by_name(db: Session, name: str) -> Role | None:
    return cast(Role | None, db.scalar(select(Role).where(Role.name == name.lower())))


def get_permissions_by_ids(db: Session, permission_ids: list[int]) -> list[Permission]:
    if not permission_ids:
        return []
    return list(
        db.scalars(select(Permission).where(Permission.id.in_(permission_ids))).all()
    )


def get_all_permissions(db: Session) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.code)).all())


def add_refresh_token(db: Session, token: RefreshToken) -> RefreshToken:
    db.add(token)
    return token


def get_refresh_token(db: Session, token_hash: str) -> RefreshToken | None:
    return cast(
        RefreshToken | None,
        db.scalar(
            select(RefreshToken)
            .options(selectinload(RefreshToken.user))
            .where(RefreshToken.token_hash == token_hash)
        ),
    )
