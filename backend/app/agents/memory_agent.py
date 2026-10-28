"""MemoryAgent: decides what to store from a conversation, returns structured ops."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from app.memory.policies import (
    detect_correction,
    detect_forget_request,
    is_sensitive,
    should_store,
)
from app.schemas.memory import MemoryCategory, MemoryOperation, MemoryOperationType

logger = logging.getLogger(__name__)

# Keywords that indicate user preference statements
_PREFERENCE_SIGNALS = [
    "i prefer", "i like", "i don't like", "i dislike", "my preference",
    "i always", "i usually", "i typically", "i want", "i need",
    "please always", "please never", "don't ever",
]

# Keywords indicating active project context
_PROJECT_SIGNALS = [
    "i'm working on", "i am working on", "my project", "we're building",
    "our project", "the project is", "current task", "sprint goal",
    "milestone", "deadline",
]

# Keywords indicating a decision was made
_DECISION_SIGNALS = [
    "we decided", "i decided", "decision:", "we chose", "i chose",
    "going with", "we will use", "we're using", "i've chosen",
    "agreed to", "the plan is",
]

# Keywords indicating user context / background
_CONTEXT_SIGNALS = [
    "i am", "i'm a", "my role", "i work as", "i work at", "my team",
    "my background", "i have experience", "i'm familiar with",
    "my company", "my organization",
]


def _classify_category(text: str) -> MemoryCategory:
    """Classify the content into a memory category."""
    text_lower = text.lower()
    if any(sig in text_lower for sig in _PREFERENCE_SIGNALS):
        return MemoryCategory.preferences
    if any(sig in text_lower for sig in _PROJECT_SIGNALS):
        return MemoryCategory.active_projects
    if any(sig in text_lower for sig in _DECISION_SIGNALS):
        return MemoryCategory.decisions
    if any(sig in text_lower for sig in _CONTEXT_SIGNALS):
        return MemoryCategory.user_context
    return MemoryCategory.user_context


class MemoryAgent:
    """
    Analyzes conversation history and answer to produce structured MemoryOperation objects.
    Does NOT write to the database directly.
    """

    def decide(
        self,
        conversation_history: List[Dict[str, str]],
        answer: str,
        user_id: str,
        existing_memories: List[Any] = None,
    ) -> List[MemoryOperation]:
        """
        Analyze conversation and decide what memory operations to perform.
        Returns a list of MemoryOperation objects only — no DB writes.
        """
        ops: List[MemoryOperation] = []
        existing = existing_memories or []

        # Examine only the most recent user messages (last 5)
        user_messages = [
            m for m in conversation_history if m.get("role") == "user"
        ][-5:]

        for msg in user_messages:
            content = msg.get("content", "").strip()
            if not content:
                continue

            # Never store sensitive content
            if is_sensitive(content):
                logger.debug("Skipping sensitive user message.")
                continue

            # Detect forget requests → DELETE ops
            is_forget, subject = detect_forget_request(content)
            if is_forget:
                subject_lower = subject.lower().strip()
                is_forget_all = any(term in subject_lower for term in ["everything", "all memories", "all my saved", "all saved", "all data"])
                subject_words = [w for w in re.findall(r"\w+", subject_lower) if len(w) > 3 and w not in {"about", "know", "please", "remember", "that", "this"}]
                for mem in existing:
                    mem_content_lower = mem.content.lower()
                    matches = (
                        is_forget_all
                        or subject_lower in mem_content_lower
                        or any(word in mem_content_lower for word in subject_words)
                    )
                    if matches:
                        ops.append(
                            MemoryOperation(
                                operation=MemoryOperationType.DELETE,
                                category=MemoryCategory(mem.category),
                                memory_id=mem.id,
                                reason=f"User requested to forget: '{subject}'",
                            )
                        )
                continue

            # Detect correction → UPDATE op
            corrected = detect_correction(content, existing)
            if corrected:
                storable, reason = should_store(content, corrected.category)
                if storable:
                    ops.append(
                        MemoryOperation(
                            operation=MemoryOperationType.UPDATE,
                            category=MemoryCategory(corrected.category),
                            content=content,
                            memory_id=corrected.id,
                            confidence=0.9,
                            reason=f"Correction detected for memory {corrected.id}",
                        )
                    )
                continue

            # Decide if content is worth storing as a new memory
            storable, reason = should_store(content, "user_context")
            if not storable:
                continue

            # Must contain at least one personal signal
            content_lower = content.lower()
            all_signals = (
                _PREFERENCE_SIGNALS + _PROJECT_SIGNALS + _DECISION_SIGNALS + _CONTEXT_SIGNALS
            )
            has_signal = any(sig in content_lower for sig in all_signals)
            if not has_signal:
                continue

            category = _classify_category(content)
            ops.append(
                MemoryOperation(
                    operation=MemoryOperationType.CREATE,
                    category=category,
                    content=content,
                    confidence=0.85,
                    reason="Extracted from user message",
                )
            )

        return ops
