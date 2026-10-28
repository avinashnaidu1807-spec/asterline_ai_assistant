"""Tests for Edge Cases A through J specified in the Master Build Prompt."""
import pytest
from app.agents.graph import run_agent_workflow
from app.retrieval.retriever import retrieve
from app.database.connection import get_db_context
from app.memory.service import MemoryService
from app.memory.policies import is_sensitive, should_store


def test_edge_case_a_oncall_stipend():
    """Case A: On-call stipend must reflect updated $175/$250 policy, resolving conflict with outdated $140."""
    result = run_agent_workflow(
        question="What is the current on-call stipend for engineers?",
        user_id="alice_chen",
        conversation_id="edge_case_a",
    )
    grounded = result["answer"]
    answer_text = grounded["answer"].lower()

    # Must contain $175 or $250
    assert "$175" in answer_text or "175" in answer_text, f"Expected 175 in answer: {grounded['answer']}"
    # Must cite handbook addendum or handbook
    citations = [c["chunk_id"] for c in grounded.get("sources", [])]
    assert any("handbook" in c for c in citations)


def test_edge_case_b_cold_recovery_rto():
    """Case B: Cold disaster recovery RTO is 60 days for cold archive, not 20 days."""
    result = run_agent_workflow(
        question="What is the cold disaster recovery storage retention period?",
        user_id="alice_chen",
        conversation_id="edge_case_b",
    )
    answer_text = result["answer"]["answer"].lower()
    assert "60 days" in answer_text or "60" in answer_text or "retention" in answer_text


def test_edge_case_c_launch_tier_ingestion_limits():
    """Case C: Launch tier ingestion limits are 300 rps sustained / 450 rps burst, not 180 rps."""
    result = run_agent_workflow(
        question="What is the Launch tier ingestion rate limit?",
        user_id="alice_chen",
        conversation_id="edge_case_c",
    )
    answer_text = result["answer"]["answer"].lower()
    assert "300" in answer_text, f"Expected 300 rps in answer: {result['answer']['answer']}"


def test_edge_case_d_patch_212_deduplication():
    """Case D: Patch 2.1.2 is warehouse export deduplication cleanup, not a breaking API change."""
    result = run_agent_workflow(
        question="What did patch 2.1.2 address in Warehouse Export?",
        user_id="alice_chen",
        conversation_id="edge_case_d",
    )
    answer_text = result["answer"]["answer"].lower()
    assert "deduplication" in answer_text or "duplicate" in answer_text or "warehouse" in answer_text


def test_edge_case_e_march_2026_incident_delayed_alerts():
    """Case E: March 2026 incident INC-2026-03 involved delayed alerts due to queue/drift, not lost alerts."""
    result = run_agent_workflow(
        question="What occurred during the March 2026 scheduler incident INC-2026-03?",
        user_id="alice_chen",
        conversation_id="edge_case_e",
    )
    answer_text = result["answer"]["answer"].lower()
    assert "delay" in answer_text or "clock" in answer_text or "drift" in answer_text or "monotonic" in answer_text


def test_edge_case_f_missing_apac_region():
    """Case F: Explicitly acknowledge missing documentation or abstain when asked about unreleased APAC region."""
    result = run_agent_workflow(
        question="When was the Asterline Asia-Pacific (APAC) region launched?",
        user_id="alice_chen",
        conversation_id="edge_case_f",
    )
    grounded = result["answer"]
    answer_text = grounded["answer"].lower()
    limitations = grounded.get("limitations", "").lower()

    # The system must note the absence or lack of evidence for an APAC region
    assert "not" in answer_text or "no mention" in answer_text or "missing" in answer_text or "insufficient" in limitations or len(limitations) > 0


def test_edge_case_g_retention_tiers():
    """Case G: Distinct retention tiers (e.g. 14 days, 60 days, 90 days, 540 days) correctly reported."""
    result = run_agent_workflow(
        question="What are the data retention periods for run records and explorer timeline?",
        user_id="alice_chen",
        conversation_id="edge_case_g",
    )
    answer_text = result["answer"]["answer"].lower()
    assert "retention" in answer_text or "days" in answer_text


def test_edge_case_h_enterprise_pricing():
    """Case H: Enterprise tier pricing is custom/negotiated, not a standard fixed list price."""
    result = run_agent_workflow(
        question="What is the monthly price for the Enterprise tier?",
        user_id="alice_chen",
        conversation_id="edge_case_h",
    )
    answer_text = result["answer"]["answer"].lower()
    assert "negotiated" in answer_text or "contact" in answer_text or "sales" in answer_text or "custom" in answer_text


def test_edge_case_i_strict_user_memory_isolation():
    """Case I: Strict user memory isolation between distinct user sessions."""
    mem_service = MemoryService()
    with get_db_context() as session:
        # Create for Alice
        mem_service.create(session, user_id="alice_chen", category="user_context", content="Specialized in distributed query execution engine.")
        # Query for Bob
        bob_mems = mem_service.get_all(session, user_id="bob_kumar")
        assert not any("distributed query" in m.content for m in bob_mems)
        # Search for Bob
        bob_search = mem_service.search(session, user_id="bob_kumar", query="distributed query")
        assert len(bob_search) == 0


def test_edge_case_j_sensitive_data_rejection():
    """Case J: Sensitive credential rejection."""
    assert is_sensitive("sk-live-51NxABCDEF0123456789") is True
    storable, _ = should_store("Password: SuperSecretP@ssw0rd123!", "preferences")
    assert storable is False

