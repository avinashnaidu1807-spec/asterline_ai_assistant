"""User Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)


class UserRead(BaseModel):
    id: str
    username: str
    display_name: str
    created_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class UserList(BaseModel):
    users: List[UserRead]
    total: int


class HealthResponse(BaseModel):
    status: str
    database: str
    vector_store: str
    llm: str
    ingestion: str
    langsmith: str
