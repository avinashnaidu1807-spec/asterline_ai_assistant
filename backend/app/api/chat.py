"""Chat API endpoint matching evaluation runner and headless clients."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import run_agent_workflow
from app.database.connection import get_db
from app.database.models import Conversation, Message, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str
    conversation_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


@router.post("")
def chat_endpoint(
    req: ChatRequest,
    db: Session = Depends(get_db),
):
    conv_id = req.conversation_id or str(uuid.uuid4())

    # Ensure user exists
    user = db.execute(select(User).where(User.id == req.user_id)).scalar_one_or_none()
    if not user:
        user = db.execute(select(User).where(User.username == req.user_id)).scalar_one_or_none()
        if not user:
            user = User(
                id=req.user_id,
                username=req.user_id,
                display_name=req.user_id.replace("_", " ").title(),
                created_at=datetime.utcnow(),
            )
            db.add(user)
            db.commit()

    # Ensure conversation exists
    conv = db.execute(select(Conversation).where(Conversation.id == conv_id)).scalar_one_or_none()
    if not conv:
        conv = Conversation(
            id=conv_id,
            user_id=user.id,
            title=req.message[:40],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(conv)
        db.commit()

    # Save user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv_id,
        role="user",
        content=req.message,
        created_at=datetime.utcnow(),
    )
    db.add(user_msg)
    db.commit()

    # Run multi-agent workflow
    final_state = run_agent_workflow(
        question=req.message,
        user_id=user.id,
        conversation_id=conv_id,
        filters=req.filters,
    )

    ans_dict = final_state.get("answer") or {}
    answer_text = ans_dict.get("answer", "No answer generated.")
    sources = ans_dict.get("sources", [])
    claims = ans_dict.get("claims", [])
    limitations = ans_dict.get("limitations", "")
    needs_clarification = ans_dict.get("needs_clarification", False)
    conflicts = final_state.get("conflicts_detected", [])

    return {
        "answer": answer_text,
        "sources": sources,
        "claims": claims,
        "limitations": [limitations] if limitations else [],
        "needs_clarification": needs_clarification,
        "conflicts": conflicts,
        "uncertainty_level": final_state.get("uncertainty_level", "low"),
        "agent_trace": final_state.get("agent_trace", []),
    }
