from ipaddress import ip_address as parse_ip_address
from typing import Any

from sqlalchemy.orm import Session

from app.features.audit.model import AuditLog


def add_audit_log(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    table_name: str,
    record_id: int | str | None = None,
    ip_address: str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
) -> AuditLog:
    try:
        normalized_ip = str(parse_ip_address(ip_address)) if ip_address else None
    except ValueError:
        normalized_ip = None

    entry = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=str(record_id) if record_id is not None else None,
        ip_address=normalized_ip,
        old_values=old_values,
        new_values=new_values,
    )
    db.add(entry)
    return entry
