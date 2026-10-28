"""LangGraph explicit multi-agent orchestration graph with LangSmith observability."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.memory_agent import MemoryAgent
from app.agents.research_agent import ResearchAgent
from app.agents.synthesis_agent import SynthesisAgent
from app.agents.verification_agent import VerificationAgent
from app.config import settings
from app.database.connection import SessionLocal
from app.database.models import Message
from app.memory.service import memory_service
from app.schemas.research import (
    AgentState,
    ChunkReference,
    Claim,
    ConflictInfo,
    GroundedAnswer,
)

logger = logging.getLogger(__name__)

# Configure LangSmith if enabled
if settings.LANGCHAIN_TRACING_V2 == "true" and settings.LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    logger.info(f"LangSmith tracing enabled for project: {settings.LANGSMITH_PROJECT}")
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

class GraphState(TypedDict):
    question: str
    user_id: str
    conversation_id: str
    filters: Optional[Dict[str, Any]]

    # Retrieval
    retrieved_chunks: List[Dict[str, Any]]
    retrieval_attempts: int

    # Verification
    verified_chunks: List[Dict[str, Any]]
    conflicts_detected: List[Dict[str, Any]]
    uncertainty_level: str
    verification_reasoning: str

    # Synthesis
    answer: Optional[Dict[str, Any]]

    # Memory
    memory_ops: List[Dict[str, Any]]
    memory_context: List[Dict[str, Any]]
    conversation_history: List[Dict[str, str]]

    # Observability
    agent_trace: List[Dict[str, Any]]
    execution_start_time: float


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

research_agent = ResearchAgent()
verification_agent = VerificationAgent()
synthesis_agent = SynthesisAgent()
memory_agent = MemoryAgent()


# ---------------------------------------------------------------------------
# Node 1: Load Context
# ---------------------------------------------------------------------------

def load_context_node(state: GraphState) -> Dict[str, Any]:
    t0 = time.time()
    user_id = state["user_id"]
    conv_id = state["conversation_id"]

    trace_entry = {
        "step": "load_context",
        "agent": "ContextLoader",
        "timestamp": time.time(),
    }

    # Load active user memories
    user_memories = []
    recent_messages = []
    with SessionLocal() as session:
        # Load memories scoped strictly to this user_id
        db_memories = memory_service.get_all(session, user_id=user_id, status="active")
        user_memories = [
            {"id": m.id, "category": m.category, "content": m.content, "confidence": m.confidence}
            for m in db_memories
        ]

        # Load recent conversation history (last 8 messages)
        history_msgs = (
            session.query(Message)
            .filter(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc())
            .limit(8)
            .all()
        )
        recent_messages = [
            {"role": m.role, "content": m.content}
            for m in reversed(history_msgs)
        ]

    trace_entry["loaded_memories_count"] = len(user_memories)
    trace_entry["loaded_history_count"] = len(recent_messages)
    trace_entry["duration_ms"] = (time.time() - t0) * 1000

    return {
        "memory_context": user_memories,
        "conversation_history": recent_messages,
        "agent_trace": state["agent_trace"] + [trace_entry],
    }


# ---------------------------------------------------------------------------
# Node 2: Research Agent
# ---------------------------------------------------------------------------

def research_node(state: GraphState) -> Dict[str, Any]:
    t0 = time.time()
    question = state["question"]
    filters = state.get("filters")
    attempts = state.get("retrieval_attempts", 0) + 1

    chunks, quality_ok, reason = research_agent.retrieve(
        question, filters=filters, top_k=settings.TOP_K_RETRIEVAL
    )

    chunks_data = [c.model_dump() for c in chunks]

    trace_entry = {
        "step": "research",
        "agent": "ResearchAgent",
        "attempt": attempts,
        "query": question,
        "retrieved_count": len(chunks),
        "chunk_ids": [c.chunk_id for c in chunks],
        "quality_ok": quality_ok,
        "quality_reason": reason,
        "duration_ms": (time.time() - t0) * 1000,
    }

    return {
        "retrieved_chunks": chunks_data,
        "retrieval_attempts": attempts,
        "agent_trace": state["agent_trace"] + [trace_entry],
    }


# ---------------------------------------------------------------------------
# Node 3: Verification Agent
# ---------------------------------------------------------------------------

def verification_node(state: GraphState) -> Dict[str, Any]:
    t0 = time.time()
    question = state["question"]
    chunk_objs = [ChunkReference(**c) for c in state["retrieved_chunks"]]

    verification_result = verification_agent.verify(question, chunk_objs)

    verified_data = [c.model_dump() for c in verification_result["verified_chunks"]]
    conflicts_data = [c.model_dump() for c in verification_result["conflicts"]]

    trace_entry = {
        "step": "verification",
        "agent": "VerificationAgent",
        "verified_count": len(verified_data),
        "conflicts_count": len(conflicts_data),
        "uncertainty_level": verification_result["uncertainty_level"],
        "reasoning": verification_result["reasoning"],
        "duration_ms": (time.time() - t0) * 1000,
    }

    return {
        "verified_chunks": verified_data,
        "conflicts_detected": conflicts_data,
        "uncertainty_level": verification_result["uncertainty_level"],
        "verification_reasoning": verification_result["reasoning"],
        "agent_trace": state["agent_trace"] + [trace_entry],
    }


# ---------------------------------------------------------------------------
# Node 4: Additional Retrieval (Conditional Retry)
# ---------------------------------------------------------------------------

def additional_retrieval_node(state: GraphState) -> Dict[str, Any]:
    t0 = time.time()
    question = state["question"]
    attempt = state.get("retrieval_attempts", 1) + 1
    reformulated = research_agent._reformulate_query(question, attempt)

    new_chunks, _, reason = research_agent.retrieve(
        reformulated, filters=state.get("filters"), top_k=settings.TOP_K_RETRIEVAL
    )

    # Merge and deduplicate with existing chunks
    existing_by_id = {c["chunk_id"]: c for c in state["retrieved_chunks"]}
    for c in new_chunks:
        if c.chunk_id not in existing_by_id:
            existing_by_id[c.chunk_id] = c.model_dump()

    merged_chunks = list(existing_by_id.values())[:settings.TOP_K_RETRIEVAL]

    trace_entry = {
        "step": "additional_retrieval",
        "agent": "ResearchAgent",
        "attempt": attempt,
        "reformulated_query": reformulated,
        "new_chunks_count": len(new_chunks),
        "total_merged": len(merged_chunks),
        "duration_ms": (time.time() - t0) * 1000,
    }

    return {
        "retrieved_chunks": merged_chunks,
        "retrieval_attempts": attempt,
        "agent_trace": state["agent_trace"] + [trace_entry],
    }


def route_retrieval_check(state: GraphState) -> str:
    """Conditional router: decide whether to retry retrieval or proceed to synthesis."""
    verified = state.get("verified_chunks", [])
    attempts = state.get("retrieval_attempts", 1)
    uncertainty = state.get("uncertainty_level", "low")

    # If 0 verified chunks and we have attempts remaining, retry
    if len(verified) == 0 and attempts < 2:
        return "retry"
    return "proceed"


# ---------------------------------------------------------------------------
# Node 5: Synthesis Agent
# ---------------------------------------------------------------------------

def synthesis_node(state: GraphState) -> Dict[str, Any]:
    t0 = time.time()
    question = state["question"]
    verified_objs = [ChunkReference(**c) for c in state["verified_chunks"]]
    conflict_objs = [ConflictInfo(**c) for c in state["conflicts_detected"]]
    memories = state.get("memory_context", [])
    uncertainty_level = state.get("uncertainty_level", "low")

    grounded_answer = synthesis_agent.synthesize(
        question=question,
        verified_chunks=verified_objs,
        conflicts=conflict_objs,
        memories=memories,
        uncertainty_level=uncertainty_level,
    )

    trace_entry = {
        "step": "synthesis",
        "agent": "SynthesisAgent",
        "provider": settings.LLM_PROVIDER,
        "claims_count": len(grounded_answer.claims),
        "sources_count": len(grounded_answer.sources),
        "needs_clarification": grounded_answer.needs_clarification,
        "duration_ms": (time.time() - t0) * 1000,
    }

    return {
        "answer": grounded_answer.model_dump(),
        "agent_trace": state["agent_trace"] + [trace_entry],
    }


# ---------------------------------------------------------------------------
# Node 6: Memory Decision Agent
# ---------------------------------------------------------------------------

def memory_decision_node(state: GraphState) -> Dict[str, Any]:
    t0 = time.time()
    user_id = state["user_id"]
    conv_history = state.get("conversation_history", []) + [
        {"role": "user", "content": state["question"]}
    ]
    answer_text = state["answer"]["answer"] if state.get("answer") else ""

    # Load current active memories for context
    with SessionLocal() as session:
        existing = memory_service.get_all(session, user_id=user_id, status="active")
        ops = memory_agent.decide(
            conversation_history=conv_history,
            answer=answer_text,
            user_id=user_id,
            existing_memories=existing,
        )

    ops_data = [op.model_dump() for op in ops]

    trace_entry = {
        "step": "memory_decision",
        "agent": "MemoryAgent",
        "decided_ops_count": len(ops_data),
        "operations": [op["operation"] for op in ops_data],
        "duration_ms": (time.time() - t0) * 1000,
    }

    return {
        "memory_ops": ops_data,
        "agent_trace": state["agent_trace"] + [trace_entry],
    }


# ---------------------------------------------------------------------------
# Node 7: Memory Persistence Node
# ---------------------------------------------------------------------------

def memory_persist_node(state: GraphState) -> Dict[str, Any]:
    t0 = time.time()
    user_id = state["user_id"]
    conv_id = state["conversation_id"]
    ops_data = state.get("memory_ops", [])

    results_data = []
    if ops_data:
        from app.schemas.memory import MemoryOperation
        typed_ops = [MemoryOperation(**op) for op in ops_data]
        with SessionLocal() as session:
            results = memory_service.apply_memory_ops(
                session=session,
                user_id=user_id,
                ops=typed_ops,
                source_conversation_id=conv_id,
            )
            session.commit()
            results_data = [r.to_dict() for r in results]

    total_execution_ms = (time.time() - state.get("execution_start_time", t0)) * 1000

    trace_entry = {
        "step": "memory_persist",
        "agent": "MemoryPersistence",
        "applied_results": results_data,
        "total_execution_ms": total_execution_ms,
        "duration_ms": (time.time() - t0) * 1000,
    }

    return {
        "agent_trace": state["agent_trace"] + [trace_entry],
    }


# ---------------------------------------------------------------------------
# Build Graph
# ---------------------------------------------------------------------------

builder = StateGraph(GraphState)

builder.add_node("load_context", load_context_node)
builder.add_node("research", research_node)
builder.add_node("verification", verification_node)
builder.add_node("additional_retrieval", additional_retrieval_node)
builder.add_node("synthesis", synthesis_node)
builder.add_node("memory_decision", memory_decision_node)
builder.add_node("memory_persist", memory_persist_node)

# Flow
builder.add_edge(START, "load_context")
builder.add_edge("load_context", "research")
builder.add_edge("research", "verification")

builder.add_conditional_edges(
    "verification",
    route_retrieval_check,
    {
        "retry": "additional_retrieval",
        "proceed": "synthesis",
    },
)

builder.add_edge("additional_retrieval", "synthesis")
builder.add_edge("synthesis", "memory_decision")
builder.add_edge("memory_decision", "memory_persist")
builder.add_edge("memory_persist", END)

research_graph = builder.compile()


def run_agent_workflow(
    question: str,
    user_id: str,
    conversation_id: str,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute the multi-agent graph with end-to-end tracing."""
    initial_state: GraphState = {
        "question": question,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "filters": filters,
        "retrieved_chunks": [],
        "retrieval_attempts": 0,
        "verified_chunks": [],
        "conflicts_detected": [],
        "uncertainty_level": "low",
        "verification_reasoning": "",
        "answer": None,
        "memory_ops": [],
        "memory_context": [],
        "conversation_history": [],
        "agent_trace": [],
        "execution_start_time": time.time(),
    }

    final_state = research_graph.invoke(initial_state)
    return final_state
