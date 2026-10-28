"""Research-related Pydantic schemas and agent state."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChunkReference(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    category: str
    published: str
    version: str
    text_snippet: str
    relevance_score: float = 0.0


class Claim(BaseModel):
    claim: str
    supporting_chunk_ids: List[str] = []
    confidence: str = Field(..., pattern="^(high|medium|low|none)$")


class GroundedAnswer(BaseModel):
    answer: str
    claims: List[Claim] = []
    limitations: str = ""
    needs_clarification: bool = False
    sources: List[ChunkReference] = []


class ResearchQuery(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    user_id: str
    conversation_id: str
    filters: Optional[Dict[str, Any]] = None


class ConflictInfo(BaseModel):
    chunk_ids: List[str]
    conflicting_values: str
    resolution: str  # which chunk_id is authoritative or "unresolved"
    resolution_reason: str


class AgentState(BaseModel):
    """Full state passed through the LangGraph pipeline."""
    question: str
    user_id: str
    conversation_id: str
    filters: Optional[Dict[str, Any]] = None

    # Retrieved chunks
    retrieved_chunks: List[ChunkReference] = []
    retrieval_attempts: int = 0

    # Verification
    verified_claims: List[Claim] = []
    conflicts_detected: List[ConflictInfo] = []
    uncertainty_level: str = "low"
    needs_more_evidence: bool = False

    # Final answer
    answer: Optional[GroundedAnswer] = None

    # Memory operations (decided by MemoryAgent, not yet persisted)
    memory_ops: List[Dict[str, Any]] = []

    # Context loaded from memories
    memory_context: List[Dict[str, Any]] = []

    # Conversation history
    conversation_history: List[Dict[str, str]] = []

    # Tracing / debug
    agent_trace: List[Dict[str, Any]] = []
