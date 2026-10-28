"""Conversations and Messages API endpoints."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.agents.graph import run_agent_workflow
from app.database.connection import get_db
from app.database.models import Conversation, Message, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationCreateReq(BaseModel):
    user_id: str
    title: str = "New Conversation"


class MessageSendReq(BaseModel):
    user_id: str
    content: str = Field(..., min_length=1, max_length=10000)


@router.get("")
def list_conversations(
    user_id: str = Query(...),
    db: Session = Depends(get_db),
):
    query = (
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.is_deleted == False)
        .order_by(desc(Conversation.updated_at))
    )
    convs = db.execute(query).scalars().all()
    results = []
    for c in convs:
        msg_count = db.query(Message).filter(Message.conversation_id == c.id).count()
        results.append({
            "id": c.id,
            "user_id": c.user_id,
            "title": c.title,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
            "message_count": msg_count,
        })
    return results


@router.post("", status_code=status.HTTP_201_CREATED)
def create_conversation(
    req: ConversationCreateReq,
    db: Session = Depends(get_db),
):
    # Verify user exists or create if needed
    user = db.execute(select(User).where(User.id == req.user_id)).scalar_one_or_none()
    if not user:
        # Check by username
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

    conv = Conversation(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=req.title,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    return {
        "id": conv.id,
        "conversation_id": conv.id,
        "user_id": conv.user_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }


@router.get("/{conv_id}")
def get_conversation(
    conv_id: str,
    db: Session = Depends(get_db),
):
    conv = db.execute(select(Conversation).where(Conversation.id == conv_id)).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = (
        db.query(Message)
        .filter(Message.conversation_id == conv_id)
        .order_by(Message.created_at)
        .all()
    )

    formatted_msgs = []
    for m in msgs:
        sources = json.loads(m.sources_json) if m.sources_json else []
        trace = json.loads(m.agent_trace_json) if m.agent_trace_json else None
        claims = trace.get("claims") if trace else []
        limitations = trace.get("limitations") if trace else None
        needs_clarification = trace.get("needs_clarification", False) if trace else False

        formatted_msgs.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
            "sources": sources,
            "claims": claims,
            "limitations": [limitations] if isinstance(limitations, str) and limitations else (limitations or []),
            "needs_clarification": needs_clarification,
            "agent_trace": trace,
        })

    return {
        "id": conv.id,
        "user_id": conv.user_id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": formatted_msgs,
    }


@router.post("/{conv_id}/messages")
def send_message(
    conv_id: str,
    req: MessageSendReq,
    db: Session = Depends(get_db),
):
    conv = db.execute(select(Conversation).where(Conversation.id == conv_id)).scalar_one_or_none()
    if not conv:
        # Create conversation automatically if it doesn't exist yet
        conv = Conversation(
            id=conv_id,
            user_id=req.user_id,
            title=req.content[:40],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(conv)
        db.commit()

    # 1. Save user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv_id,
        role="user",
        content=req.content,
        created_at=datetime.utcnow(),
    )
    db.add(user_msg)
    conv.updated_at = datetime.utcnow()
    db.commit()

    # Update conversation title if it's the first message
    if conv.title == "New Conversation":
        conv.title = req.content[:40].strip()
        db.commit()

    # 2. Execute multi-agent graph workflow
    final_state = run_agent_workflow(
        question=req.content,
        user_id=req.user_id,
        conversation_id=conv_id,
    )

    grounded_ans = final_state.get("answer") or {}
    answer_text = grounded_ans.get("answer", "No answer generated.")
    sources = grounded_ans.get("sources", [])
    claims = grounded_ans.get("claims", [])
    limitations = grounded_ans.get("limitations", "")
    needs_clarification = grounded_ans.get("needs_clarification", False)

    trace_summary = {
        "claims": claims,
        "limitations": limitations,
        "needs_clarification": needs_clarification,
        "uncertainty_level": final_state.get("uncertainty_level", "low"),
        "steps": [t.get("step") for t in final_state.get("agent_trace", [])],
        "conflicts_detected": len(final_state.get("conflicts_detected", [])) > 0,
        "memory_ops": [op.get("operation") for op in final_state.get("memory_ops", [])],
    }

    # 3. Save assistant message
    asst_msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conv_id,
        role="assistant",
        content=answer_text,
        created_at=datetime.utcnow(),
        sources_json=json.dumps(sources),
        agent_trace_json=json.dumps(trace_summary),
    )
    db.add(asst_msg)
    conv.updated_at = datetime.utcnow()
    db.commit()

    return {
        "id": asst_msg.id,
        "role": asst_msg.role,
        "content": asst_msg.content,
        "created_at": asst_msg.created_at.isoformat(),
        "sources": sources,
        "claims": claims,
        "limitations": [limitations] if limitations else [],
        "needs_clarification": needs_clarification,
        "agent_trace": trace_summary,
    }
