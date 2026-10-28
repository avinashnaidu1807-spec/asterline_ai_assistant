"""Tests for persistent user memory: strict user isolation, policies, sensitivity checks, corrections, and forget requests."""
import pytest
from app.database.connection import get_db_context
from app.database.models import User, Memory
from app.memory.service import MemoryService
from app.memory.policies import should_store, is_sensitive, is_redundant, detect_correction, detect_forget_request


@pytest.fixture
def memory_service():
    return MemoryService()


def test_per_user_isolation(memory_service):
    """Verify that User A's memories are strictly isolated from User B."""
    user_a = "alice_chen"
    user_b = "bob_kumar"

    with get_db_context() as session:
        # Alice creates a preference
        res_a = memory_service.create(
            session,
            user_id=user_a,
            category="preferences",
            content="Prefers concise bullet point summaries for architecture reviews."
        )
        assert res_a.success is True
        alice_mem_id = res_a.memory.id

        # Bob's memory query must not see Alice's memory
        bob_memories = memory_service.get_all(session, user_id=user_b)
        assert not any(m.id == alice_mem_id for m in bob_memories)
        assert not any("bullet point" in m.content for m in bob_memories)

        # Bob search query must not see Alice's memory
        bob_search = memory_service.search(session, user_id=user_b, query="bullet points")
        assert not any(m.id == alice_mem_id for m in bob_search)

        # Bob attempting to update Alice's memory must fail
        hack_res = memory_service.update(
            session,
            memory_id=alice_mem_id,
            user_id=user_b,
            content="Malicious override"
        )
        assert hack_res.success is False
        assert "not owned by user" in hack_res.reason or "not found" in hack_res.reason

        # Bob attempting to delete Alice's memory must fail
        del_res = memory_service.delete(session, memory_id=alice_mem_id, user_id=user_b)
        assert del_res.success is False

        # Alice can retrieve her own memory
        alice_mem = memory_service.get_one(session, memory_id=alice_mem_id, user_id=user_a)
        assert alice_mem is not None
        assert "bullet point" in alice_mem.content

        # Cleanup
        memory_service.delete(session, memory_id=alice_mem_id, user_id=user_a)


def test_sensitive_data_rejection(memory_service):
    """Verify that sensitive credentials, API keys, and passwords are strictly rejected."""
    sensitive_examples = [
        "My Asterline API key: sk-abcdef1234567890abcdef12345",
        "My database password is: superSecretPassword!123",
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "My private_key is MIIEvgIBADANBgkqhkiG9w0BAQEFAASC",
        "User credit card number: 4532 1234 5678 9010",
    ]

    with get_db_context() as session:
        for item in sensitive_examples:
            assert is_sensitive(item) is True
            storable, reason = should_store(item, "user_context")
            assert storable is False
            assert "sensitive" in reason.lower()

            # Service level rejection
            res = memory_service.create(session, user_id="carol_reyes", category="user_context", content=item)
            assert res.success is False
            assert "sensitive" in res.reason.lower()


def test_ai_answer_non_authoritative_rejection(memory_service):
    """Verify AI-generated company documentation assertions are rejected from user memory."""
    ai_statements = [
        "According to the documentation, Launch tier limit is 300 rps.",
        "Based on the evidence from handbook, on-call stipend is $175.",
        "Sources indicate that cold recovery takes 60 days.",
    ]
    for statement in ai_statements:
        storable, reason = should_store(statement, "user_context")
        assert storable is False
        assert "ai-generated" in reason.lower() or "not user context" in reason.lower()


def test_memory_correction_flow(memory_service):
    """Verify that stating a correction updates the old memory and sets provenance."""
    user = "alice_chen"

    with get_db_context() as session:
        # Initial preference
        res1 = memory_service.create(
            session,
            user_id=user,
            category="preferences",
            content="Primary working timezone is US Pacific PST time."
        )
        assert res1.success is True
        mem1_id = res1.memory.id

        # User corrects preference
        res2 = memory_service.create(
            session,
            user_id=user,
            category="preferences",
            content="Actually my primary working timezone is now US Eastern EST time."
        )
        assert res2.success is True
        assert "correction" in res2.reason.lower()

        # Verify old memory is marked as corrected
        old_mem = memory_service.get_one(session, memory_id=mem1_id, user_id=user)
        assert old_mem.status == "corrected"

        # Cleanup
        memory_service.delete(session, memory_id=mem1_id, user_id=user)
        if res2.memory:
            memory_service.delete(session, memory_id=res2.memory.id, user_id=user)


def test_forget_request_handling():
    """Verify forget requests detect the target topic."""
    forget_prompts = [
        ("Please forget about my staging credentials", "my staging credentials"),
        ("Don't remember my personal phone number", "my personal phone number"),
        ("Stop remembering my home address", "my home address"),
    ]
    for prompt, expected_sub in forget_prompts:
        is_forget, target = detect_forget_request(prompt)
        assert is_forget is True
        assert expected_sub in target.lower()

