"""MemoryService: orchestrates repository + policies with user_id ownership validation."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.database.models import Memory
from app.memory import policies, repository
from app.schemas.memory import MemoryCategory, MemoryOperation, MemoryOperationType

logger = logging.getLogger(__name__)


class MemoryOperationResult:
    def __init__(self, success: bool, reason: str, memory: Optional[Memory] = None, count: int = 0):
        self.success = success
        self.reason = reason
        self.memory = memory
        self.count = count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "reason": self.reason,
            "memory_id": self.memory.id if self.memory else None,
            "count": self.count,
        }


class MemoryService:
    """Orchestrates memory operations with policy enforcement and ownership validation."""

    def create(
        self,
        session: Session,
        user_id: str,
        category: str,
        content: str,
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        confidence: float = 1.0,
        provenance: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> MemoryOperationResult:
        storable, reason = policies.should_store(content, category)
        if not storable:
            return MemoryOperationResult(success=False, reason=reason)

        existing = repository.get_memories(session, user_id, category=category)
        if policies.is_redundant(content, existing):
            return MemoryOperationResult(success=False, reason="Memory is redundant with existing entry")

        all_memories = repository.get_memories(session, user_id)
        corrected = policies.detect_correction(content, all_memories)
        if corrected:
            repository.update_memory(session, corrected.id, user_id, status="corrected")
            memory = repository.create_memory(
                session, user_id, category, content,
                source_conversation_id=source_conversation_id,
                source_message_id=source_message_id,
                confidence=confidence,
                provenance=f"correction_of:{corrected.id}" if provenance is None else provenance,
                expires_at=expires_at,
            )
            return MemoryOperationResult(success=True, reason="Correction applied", memory=memory)

        memory = repository.create_memory(
            session, user_id, category, content,
            source_conversation_id=source_conversation_id,
            source_message_id=source_message_id,
            confidence=confidence,
            provenance=provenance,
            expires_at=expires_at,
        )
        return MemoryOperationResult(success=True, reason="Memory created", memory=memory)

    def get_all(
        self,
        session: Session,
        user_id: str,
        category: Optional[str] = None,
        status: str = "active",
    ) -> List[Memory]:
        return repository.get_memories(session, user_id, category=category, status=status)

    def get_one(
        self,
        session: Session,
        memory_id: str,
        user_id: str,
    ) -> Optional[Memory]:
        return repository.get_memory_by_id(session, memory_id, user_id)

    def update(
        self,
        session: Session,
        memory_id: str,
        user_id: str,
        content: Optional[str] = None,
        status: Optional[str] = None,
        confidence: Optional[float] = None,
        expires_at: Optional[datetime] = None,
    ) -> MemoryOperationResult:
        if content and policies.is_sensitive(content):
            return MemoryOperationResult(success=False, reason="Content contains sensitive data")

        memory = repository.update_memory(
            session, memory_id, user_id,
            content=content, status=status, confidence=confidence, expires_at=expires_at,
        )
        if memory is None:
            return MemoryOperationResult(success=False, reason="Memory not found or not owned by user")
        return MemoryOperationResult(success=True, reason="Memory updated", memory=memory)

    def delete(
        self,
        session: Session,
        memory_id: str,
        user_id: str,
    ) -> MemoryOperationResult:
        deleted = repository.delete_memory(session, memory_id, user_id)
        if not deleted:
            return MemoryOperationResult(success=False, reason="Memory not found or not owned by user")
        return MemoryOperationResult(success=True, reason="Memory deleted")

    def delete_all(
        self,
        session: Session,
        user_id: str,
    ) -> MemoryOperationResult:
        count = repository.delete_all_memories(session, user_id)
        return MemoryOperationResult(success=True, reason=f"Deleted {count} memories", count=count)

    def search(
        self,
        session: Session,
        user_id: str,
        query: str,
    ) -> List[Memory]:
        return repository.search_memories(session, user_id, query)

    def apply_memory_ops(
        self,
        session: Session,
        user_id: str,
        ops: List[MemoryOperation],
        source_conversation_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
    ) -> List[MemoryOperationResult]:
        results = []
        for op in ops:
            if not policies.validate_memory_op(op.operation.value, user_id, op.memory_id):
                results.append(MemoryOperationResult(success=False, reason=f"Invalid operation: {op.operation}"))
                continue

            if op.operation == MemoryOperationType.CREATE:
                result = self.create(
                    session, user_id, op.category.value, op.content or "",
                    source_conversation_id=source_conversation_id,
                    source_message_id=source_message_id,
                    confidence=op.confidence,
                    provenance=op.reason or "agent_extracted",
                )
                results.append(result)

            elif op.operation == MemoryOperationType.UPDATE:
                result = self.update(
                    session, op.memory_id, user_id,
                    content=op.content,
                    confidence=op.confidence if op.confidence != 1.0 else None,
                )
                results.append(result)

            elif op.operation == MemoryOperationType.DELETE:
                result = self.delete(session, op.memory_id, user_id)
                results.append(result)

        return results


memory_service = MemoryService()
