from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.core.dependencies import DatabaseSession, require_permission
from app.features.audit.model import AuditLog
from app.features.audit.schemas import AuditLogResponse
from app.features.users.model import User

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", response_model=list[AuditLogResponse])
def get_audit_logs(
    db: DatabaseSession,
    actor: User = Depends(require_permission("audit.read")),
    user_id: int | None = None,
    action: str | None = None,
    table_name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    statement = select(AuditLog)
    if user_id is not None:
        statement = statement.where(AuditLog.user_id == user_id)
    if action is not None:
        statement = statement.where(AuditLog.action == action)
    if table_name is not None:
        statement = statement.where(AuditLog.table_name == table_name)
    if date_from is not None:
        statement = statement.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        statement = statement.where(AuditLog.created_at <= date_to)
    statement = statement.order_by(AuditLog.created_at.desc()).offset((page - 1) * size).limit(size)
    return list(db.scalars(statement).all())
