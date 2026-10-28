"""Tests for individual agents: ResearchAgent, VerificationAgent, SynthesisAgent, MemoryAgent."""
import pytest
from app.agents.research_agent import ResearchAgent
from app.agents.verification_agent import VerificationAgent
from app.agents.synthesis_agent import SynthesisAgent
from app.agents.memory_agent import MemoryAgent
from app.schemas.research import ChunkReference


def test_research_agent_retrieves_chunks():
    """Verify research agent retrieves relevant chunks and provides quality assessment."""
    agent = ResearchAgent()
    chunks, quality_ok, reason = agent.retrieve("What is the on-call stipend policy?")
    assert len(chunks) > 0
    assert quality_ok is True
    first_chunk = chunks[0]
    assert hasattr(first_chunk, "chunk_id")
    assert hasattr(first_chunk, "title")


def test_verification_agent_detects_conflicts():
    """Verify verification agent detects supersession and conflicting facts."""
    agent = VerificationAgent()
    sample_chunks = [
        ChunkReference(
            chunk_id="handbook:2",
            doc_id="handbook",
            title="Employee Handbook",
            category="hr",
            version="1.0",
            published="2024-01-01",
            text_snippet="The on-call stipend is $140 per week for on-duty engineers.",
            relevance_score=0.9
        ),
        ChunkReference(
            chunk_id="handbook-addendum:1",
            doc_id="handbook-addendum",
            title="Employee Handbook 2025 Addendum",
            category="hr",
            version="2.0",
            published="2025-01-15",
            text_snippet="Supersedes earlier handbook policies. The on-call stipend is updated to $175 on weekdays and $250 on weekends.",
            relevance_score=0.95
        )
    ]
    result = agent.verify("What is the on-call stipend?", sample_chunks)
    assert len(result["conflicts"]) >= 1
    assert result["conflicts"][0].resolution == "handbook-addendum:1"
    assert "supersess" in result["conflicts"][0].resolution_reason.lower()


def test_synthesis_agent_formats_answer_and_citations():
    """Verify synthesis agent compiles answer with citations and limitations."""
    agent = SynthesisAgent()
    sample_chunks = [
        ChunkReference(
            chunk_id="handbook-addendum:1",
            doc_id="handbook-addendum",
            title="Employee Handbook 2025 Addendum",
            category="hr",
            version="2.0",
            published="2025-01-15",
            text_snippet="The on-call stipend is updated to $175 on weekdays and $250 on weekends.",
            relevance_score=0.95
        )
    ]
    answer = agent.synthesize(
        question="What is the on-call stipend?",
        verified_chunks=sample_chunks,
        conflicts=[],
        memories=[],
        uncertainty_level="low"
    )
    assert len(answer.answer) > 0
    assert len(answer.sources) > 0
    assert answer.sources[0].chunk_id == "handbook-addendum:1"
    assert "$175" in answer.answer or "175" in answer.answer


def test_memory_agent_extracts_preferences():
    """Verify memory agent identifies user preferences and extracts memory ops."""
    agent = MemoryAgent()
    history = [
        {"role": "user", "content": "Please note that I prefer concise responses with bullet points."},
        {"role": "assistant", "content": "Understood. I will provide concise responses with bullet points."}
    ]
    ops = agent.decide(
        conversation_history=history,
        answer="Understood. I will provide concise responses.",
        user_id="alice_chen",
        existing_memories=[]
    )
    assert len(ops) >= 1
    op = ops[0]
    assert op.operation.value.upper() == "CREATE"
    assert "concise" in op.content.lower() or "bullet" in op.content.lower()
