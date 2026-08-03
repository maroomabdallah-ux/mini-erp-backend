from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, IPvAnyAddress


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    action: str
    table_name: str
    record_id: str | None
    ip_address: IPvAnyAddress | None
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
