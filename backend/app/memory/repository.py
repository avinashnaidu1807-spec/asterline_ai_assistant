"""Memory database operations — all parameterized, no raw SQL injection possible."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.database.models import Memory

logger = logging.getLogger(__name__)


def create_memory(
    session: Session,
    user_id: str,
    category: str,
    content: str,
    source_conversation_id: Optional[str] = None,
    source_message_id: Optional[str] = None,
    confidence: float = 1.0,
    provenance: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> Memory:
    memory = Memory(
        id=str(uuid.uuid4()),
        user_id=user_id,
        category=category,
        content=content,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
        confidence=confidence,
        status="active",
        provenance=provenance,
        expires_at=expires_at,
    )
    session.add(memory)
    session.flush()
    return memory


def get_memories(
    session: Session,
    user_id: str,
    category: Optional[str] = None,
    status: str = "active",
) -> List[Memory]:
    conditions = [
        Memory.user_id == user_id,
        Memory.status == status,
    ]
    if category is not None:
        conditions.append(Memory.category == category)
    result = session.execute(
        select(Memory).where(and_(*conditions)).order_by(Memory.updated_at.desc())
    )
    return list(result.scalars().all())


def get_memory_by_id(
    session: Session,
    memory_id: str,
    user_id: str,
) -> Optional[Memory]:
    result = session.execute(
        select(Memory).where(
            and_(Memory.id == memory_id, Memory.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


def update_memory(
    session: Session,
    memory_id: str,
    user_id: str,
    content: Optional[str] = None,
    status: Optional[str] = None,
    confidence: Optional[float] = None,
    expires_at: Optional[datetime] = None,
) -> Optional[Memory]:
    memory = get_memory_by_id(session, memory_id, user_id)
    if memory is None:
        return None
    if content is not None:
        memory.content = content
    if status is not None:
        memory.status = status
    if confidence is not None:
        memory.confidence = confidence
    if expires_at is not None:
        memory.expires_at = expires_at
    memory.updated_at = datetime.utcnow()
    session.flush()
    return memory


def delete_memory(
    session: Session,
    memory_id: str,
    user_id: str,
) -> bool:
    memory = get_memory_by_id(session, memory_id, user_id)
    if memory is None:
        return False
    session.delete(memory)
    session.flush()
    return True


def delete_all_memories(
    session: Session,
    user_id: str,
) -> int:
    result = session.execute(
        select(Memory).where(Memory.user_id == user_id)
    )
    memories = list(result.scalars().all())
    count = len(memories)
    for m in memories:
        session.delete(m)
    session.flush()
    return count


def search_memories(
    session: Session,
    user_id: str,
    query: str,
) -> List[Memory]:
    """Case-insensitive text search over memory content for active memories."""
    result = session.execute(
        select(Memory).where(
            and_(
                Memory.user_id == user_id,
                Memory.status == "active",
                Memory.content.ilike(f"%{query}%"),
            )
        ).order_by(Memory.updated_at.desc())
    )
    return list(result.scalars().all())


def find_similar_memories(
    session: Session,
    user_id: str,
    content: str,
    threshold: float = 0.8,
) -> List[Memory]:
    """Find memories with substantial textual overlap for deduplication check."""
    memories = get_memories(session, user_id, status="active")
    content_words = set(content.lower().split())
    similar = []
    for memory in memories:
        mem_words = set(memory.content.lower().split())
        if not content_words or not mem_words:
            continue
        intersection = content_words & mem_words
        union = content_words | mem_words
        jaccard = len(intersection) / len(union)
        if jaccard >= threshold:
            similar.append(memory)
    return similar
