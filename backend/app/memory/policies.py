"""Memory write policy evaluator."""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.database.models import Memory

# Patterns indicating sensitive data
_SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|secret|api[_\s]?key|token|credential|ssn|social\s?security|credit\s?card|cvv)\s*[:=\s]\s*\S+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),  # API key pattern
    re.compile(r"(?i)private[_\s]?key"),
]

# Patterns for "forget X" requests
_FORGET_PATTERNS = [
    re.compile(r"(?i)forget\s+(?:about\s+)?(.+)"),
    re.compile(r"(?i)don'?t\s+remember\s+(.+)"),
    re.compile(r"(?i)stop\s+remembering\s+(.+)"),
    re.compile(r"(?i)remove\s+(?:that\s+)?memory\s+(?:about\s+)?(.+)"),
    re.compile(r"(?i)delete\s+(?:the\s+)?memory\s+(?:about\s+)?(.+)"),
]

# Minimum content length to bother storing
_MIN_CONTENT_LENGTH = 10

# Categories that should never store AI-generated answer content
_AI_ANSWER_INDICATORS = [
    "according to the documentation",
    "based on the evidence",
    "the retrieved chunks indicate",
    "sources indicate",
    "as stated in",
]


def should_store(content: str, category: str) -> Tuple[bool, str]:
    """
    Evaluate whether content is worth storing as a memory.
    Returns (should_store: bool, reason: str).
    """
    if not content or len(content.strip()) < _MIN_CONTENT_LENGTH:
        return False, "Content too short to be meaningful"

    if is_sensitive(content):
        return False, "Content contains sensitive data and will not be stored"

    # Don't store transient or trivial content
    content_lower = content.lower().strip()
    trivial_phrases = ["ok", "thanks", "yes", "no", "sure", "got it", "okay", "hi", "hello"]
    if content_lower in trivial_phrases:
        return False, "Content is trivial and not worth storing"

    # Don't store AI-generated answer content as factual memories
    for indicator in _AI_ANSWER_INDICATORS:
        if indicator in content_lower:
            return False, "Content appears to be AI-generated answer text, not user context"

    return True, "Content is suitable for storage"


def is_sensitive(content: str) -> bool:
    """Detect passwords, API keys, credentials, and PII."""
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(content):
            return True
    return False


def is_redundant(content: str, existing_memories: List[Memory]) -> bool:
    """Check if content is substantially similar to an existing memory."""
    content_words = set(content.lower().split())
    for memory in existing_memories:
        if memory.status != "active":
            continue
        mem_words = set(memory.content.lower().split())
        if not content_words or not mem_words:
            continue
        intersection = content_words & mem_words
        union = content_words | mem_words
        jaccard = len(intersection) / len(union)
        if jaccard >= 0.75:
            return True
    return False


def detect_correction(content: str, existing_memories: List[Memory]) -> Optional[Memory]:
    """
    Detect if this content is correcting an existing memory.
    Returns the memory being corrected, or None.
    """
    correction_signals = [
        "actually", "correction:", "to clarify", "not", "wrong", "incorrect",
        "update:", "changed to", "is now", "was incorrect",
    ]
    content_lower = content.lower()
    has_correction_signal = any(sig in content_lower for sig in correction_signals)
    if not has_correction_signal:
        return None

    # Find the most similar existing memory
    content_words = set(content_lower.split())
    best_match: Optional[Memory] = None
    best_score = 0.35  # threshold for matching corrected memory

    for memory in existing_memories:
        if memory.status != "active":
            continue
        mem_words = set(memory.content.lower().split())
        if not mem_words:
            continue
        intersection = content_words & mem_words
        union = content_words | mem_words
        jaccard = len(intersection) / len(union)
        if jaccard > best_score:
            best_score = jaccard
            best_match = memory

    return best_match


def detect_forget_request(content: str) -> Tuple[bool, str]:
    """
    Detect "forget X" patterns.
    Returns (is_forget_request: bool, what_to_forget: str).
    """
    for pattern in _FORGET_PATTERNS:
        match = pattern.search(content)
        if match:
            subject = match.group(1).strip().rstrip(".")
            return True, subject
    return False, ""


def validate_memory_op(operation: str, user_id: str, memory_id: Optional[str] = None) -> bool:
    """
    Allowlist validation for memory operations.
    Only CREATE, UPDATE, DELETE are allowed.
    """
    allowed_operations = {"CREATE", "UPDATE", "DELETE"}
    if operation not in allowed_operations:
        return False
    if not user_id or not user_id.strip():
        return False
    if operation in {"UPDATE", "DELETE"} and (not memory_id or not memory_id.strip()):
        return False
    return True
