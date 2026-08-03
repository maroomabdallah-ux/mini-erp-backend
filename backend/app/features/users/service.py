from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.features.audit.service import add_audit_log
from app.features.users import business, repository
from app.features.users.exceptions import UserNotFoundError
from app.features.users.model import Permission, Role, User
from app.features.users.schemas import RoleCreate, RoleUpdate, UserCreate, UserUpdate


def _roles_or_error(db: Session, role_ids: list[int]) -> list[Role]:
    roles = repository.get_roles_by_ids(db, role_ids)
    missing = sorted(set(role_ids) - {role.id for role in roles})
    if missing:
        raise NotFoundError(f"Roles not found: {missing}.")
    inactive = [role.id for role in roles if not role.is_active]
    if inactive:
        from app.core.exceptions import BusinessRuleError

        raise BusinessRuleError(f"Inactive roles cannot be assigned: {inactive}.")
    return roles


def get_users(
    db: Session, page: int = 1, size: int = 20, search: str | None = None
) -> dict:
    return {
        "items": repository.get_all_users(
            db, offset=(page - 1) * size, limit=size, search=search
        ),
        "page": page,
        "size": size,
        "total": repository.count_users(db, search=search),
    }


def get_user(db: Session, user_id: int) -> User:
    user = repository.get_user_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError(user_id)
    return user


def create_user(
    db: Session,
    data: UserCreate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> User:
    business.ensure_email_is_available(
        repository.get_user_by_email(db, str(data.email)), str(data.email)
    )
    business.ensure_username_is_available(
        repository.get_user_by_username(db, data.username), data.username
    )
    business.validate_password(data.password)
    roles = _roles_or_error(db, data.role_ids)
    user = User(
        username=data.username.lower(),
        first_name=data.first_name,
        last_name=data.last_name,
        email=str(data.email).lower(),
        hashed_password=hash_password(data.password),
        roles=roles,
    )
    try:
        repository.add_user(db, user)
        db.flush()
        add_audit_log(
            db,
            user_id=actor_id,
            action="create",
            table_name="users",
            record_id=user.id,
            ip_address=ip_address,
            new_values={"username": user.username, "email": user.email},
        )
        db.commit()
        return get_user(db, user.id)
    except (IntegrityError, SQLAlchemyError):
        db.rollback()
        raise


def update_user(
    db: Session,
    user_id: int,
    data: UserUpdate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> User:
    user = get_user(db, user_id)
    old_values = {
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role_ids": [role.id for role in user.roles],
    }
    if data.email is not None and str(data.email).lower() != user.email:
        email = str(data.email).lower()
        business.ensure_email_is_available(repository.get_user_by_email(db, email), email)
        user.email = email
    if data.username is not None and data.username.lower() != user.username:
        username = data.username.lower()
        business.ensure_username_is_available(
            repository.get_user_by_username(db, username), username
        )
        user.username = username
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.role_ids is not None:
        user.roles = _roles_or_error(db, data.role_ids)
    try:
        repository.save_user(db, user)
        add_audit_log(
            db,
            user_id=actor_id,
            action="update",
            table_name="users",
            record_id=user.id,
            ip_address=ip_address,
            old_values=old_values,
            new_values={
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role_ids": [role.id for role in user.roles],
            },
        )
        db.commit()
        return get_user(db, user.id)
    except SQLAlchemyError:
        db.rollback()
        raise


def deactivate_user(
    db: Session,
    user_id: int,
    *,
    actor_id: int,
    ip_address: str | None,
) -> User:
    user = get_user(db, user_id)
    business.ensure_user_can_be_deactivated(user, actor_id=actor_id)
    user.is_active = False
    add_audit_log(
        db,
        user_id=actor_id,
        action="deactivate",
        table_name="users",
        record_id=user.id,
        ip_address=ip_address,
        old_values={"is_active": True},
        new_values={"is_active": False},
    )
    db.commit()
    return get_user(db, user.id)


def reset_user_password(
    db: Session,
    user_id: int,
    new_password: str,
    *,
    actor_id: int,
    ip_address: str | None,
) -> User:
    user = get_user(db, user_id)
    business.validate_password(new_password)
    user.hashed_password = hash_password(new_password)
    add_audit_log(
        db,
        user_id=actor_id,
        action="reset_password",
        table_name="users",
        record_id=user.id,
        ip_address=ip_address,
    )
    db.commit()
    return get_user(db, user.id)


def get_roles(db: Session) -> list[Role]:
    return repository.get_all_roles(db)


def get_permissions(db: Session) -> list[Permission]:
    return repository.get_all_permissions(db)


def get_role(db: Session, role_id: int) -> Role:
    role = repository.get_role_by_id(db, role_id)
    if role is None:
        raise NotFoundError(f"Role with id {role_id} was not found.")
    return role


def create_role(
    db: Session, data: RoleCreate, *, actor_id: int, ip_address: str | None
) -> Role:
    if repository.get_role_by_name(db, data.name):
        from app.core.exceptions import ConflictError

        raise ConflictError(f"Role '{data.name}' already exists.")
    role = Role(name=data.name.lower(), description=data.description)
    db.add(role)
    db.flush()
    add_audit_log(
        db,
        user_id=actor_id,
        action="create",
        table_name="roles",
        record_id=role.id,
        ip_address=ip_address,
        new_values={"name": role.name},
    )
    db.commit()
    return repository.get_role_by_id(db, role.id)  # type: ignore[return-value]


def update_role(
    db: Session,
    role_id: int,
    data: RoleUpdate,
    *,
    actor_id: int,
    ip_address: str | None,
) -> Role:
    from app.core.exceptions import BusinessRuleError, ConflictError

    role = get_role(db, role_id)
    old_values = {"name": role.name, "description": role.description}
    if data.name is not None and data.name != role.name:
        if role.name == "admin":
            raise BusinessRuleError("The built-in admin role cannot be renamed.")
        if repository.get_role_by_name(db, data.name):
            raise ConflictError(f"Role '{data.name}' already exists.")
        role.name = data.name
    if "description" in data.model_fields_set:
        role.description = data.description
    add_audit_log(
        db,
        user_id=actor_id,
        action="update",
        table_name="roles",
        record_id=role.id,
        ip_address=ip_address,
        old_values=old_values,
        new_values={"name": role.name, "description": role.description},
    )
    db.commit()
    return get_role(db, role.id)


def deactivate_role(
    db: Session, role_id: int, *, actor_id: int, ip_address: str | None
) -> Role:
    from app.core.exceptions import BusinessRuleError

    role = get_role(db, role_id)
    if role.name == "admin":
        raise BusinessRuleError("The built-in admin role cannot be deactivated.")
    if not role.is_active:
        raise BusinessRuleError(f"Role with id {role_id} is already inactive.")
    role.is_active = False
    add_audit_log(
        db,
        user_id=actor_id,
        action="deactivate",
        table_name="roles",
        record_id=role.id,
        ip_address=ip_address,
        old_values={"is_active": True},
        new_values={"is_active": False},
    )
    db.commit()
    return get_role(db, role.id)


def assign_permissions(
    db: Session,
    role_id: int,
    permission_ids: list[int],
    *,
    actor_id: int,
    ip_address: str | None,
) -> Role:
    role = repository.get_role_by_id(db, role_id)
    if role is None:
        raise NotFoundError(f"Role with id {role_id} was not found.")
    permissions = repository.get_permissions_by_ids(db, permission_ids)
    missing = sorted(set(permission_ids) - {item.id for item in permissions})
    if missing:
        raise NotFoundError(f"Permissions not found: {missing}.")
    if role.name == "admin":
        required = {"users.manage", "roles.manage", "audit.read"}
        assigned_codes = {item.code for item in permissions}
        if not required <= assigned_codes:
            from app.core.exceptions import BusinessRuleError

            raise BusinessRuleError(
                "The admin role must retain users.manage, roles.manage, and audit.read."
            )
    old_ids = [item.id for item in role.permissions]
    role.permissions = permissions
    add_audit_log(
        db,
        user_id=actor_id,
        action="assign_permissions",
        table_name="roles",
        record_id=role.id,
        ip_address=ip_address,
        old_values={"permission_ids": old_ids},
        new_values={"permission_ids": permission_ids},
    )
    db.commit()
    return repository.get_role_by_id(db, role.id)  # type: ignore[return-value]
