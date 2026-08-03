# app/core/responses.py

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str
    code: str
    field_errors: dict[str, Any] = Field(
        default_factory=dict
    )


class MessageResponse(BaseModel):
    message: str