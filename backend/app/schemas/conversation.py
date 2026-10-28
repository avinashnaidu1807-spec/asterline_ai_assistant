"""Conversation and Message Pydantic schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1, max_length=10000)
    sources_json: Optional[str] = None
    agent_trace_json: Optional[str] = None


class MessageRead(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    sources_json: Optional[str] = None
    agent_trace_json: Optional[str] = None

    model_config = {"from_attributes": True}


class ConversationCreate(BaseModel):
    user_id: str
    title: str = Field(default="New Conversation", max_length=500)
    metadata_json: Optional[str] = None


class ConversationRead(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    metadata_json: Optional[str] = None
    is_deleted: bool = False
    messages: List[MessageRead] = []

    model_config = {"from_attributes": True}


class ConversationList(BaseModel):
    conversations: List[ConversationRead]
    total: int
