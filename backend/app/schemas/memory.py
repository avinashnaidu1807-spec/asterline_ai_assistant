"""Memory Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MemoryCategory(str, Enum):
    preferences = "preferences"
    user_context = "user_context"
    active_projects = "active_projects"
    decisions = "decisions"
    conversation_summaries = "conversation_summaries"


class MemoryOperationType(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class MemoryCreate(BaseModel):
    user_id: str
    category: MemoryCategory
    content: str = Field(..., min_length=1, max_length=5000)
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: Optional[str] = None
    expires_at: Optional[datetime] = None


class MemoryRead(BaseModel):
    id: str
    user_id: str
    category: str
    content: str
    created_at: datetime
    updated_at: datetime
    source_conversation_id: Optional[str] = None
    source_message_id: Optional[str] = None
    confidence: float
    status: str
    provenance: Optional[str] = None
    expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MemoryUpdate(BaseModel):
    content: Optional[str] = Field(default=None, min_length=1, max_length=5000)
    category: Optional[MemoryCategory] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    status: Optional[str] = Field(default=None, pattern="^(active|corrected|deleted)$")
    expires_at: Optional[datetime] = None


class MemoryList(BaseModel):
    memories: List[MemoryRead]
    total: int


class MemoryOperation(BaseModel):
    """Structured memory operation returned by MemoryAgent."""
    operation: MemoryOperationType
    category: MemoryCategory
    content: Optional[str] = None
    memory_id: Optional[str] = None  # for UPDATE / DELETE
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str = ""
