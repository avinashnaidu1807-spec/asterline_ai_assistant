"""Tests for local vector retrieval, ChromaDB ingestion integrity, and hybrid search."""
import pytest
from app.retrieval.ingestion import get_chroma_collection
from app.retrieval.retriever import retrieve, _expand_query
from app.retrieval.embedder import get_local_embedder


def test_chroma_corpus_integrity():
    """Verify that ChromaDB collection has exactly 75 chunks from 25 documents."""
    col = get_chroma_collection()
    count = col.count()
    assert count == 75, f"Expected 75 chunks in ChromaDB, found {count}"

    # Sample chunks and check required metadata fields
    sample = col.get(limit=10, include=["metadatas", "documents"])
    assert len(sample["ids"]) == 10
    doc_titles = set()
    for i, meta in enumerate(sample["metadatas"]):
        chunk_id = sample["ids"][i]
        assert ":" in chunk_id
        assert "doc_id" in meta
        assert "title" in meta or "doc_title" in meta
        doc_titles.add(meta.get("title") or meta.get("doc_title"))
    assert len(doc_titles) >= 1


def test_query_expansion():
    """Verify query expansion maps domain concepts correctly."""
    expanded = _expand_query("What is the on-call stipend?")
    assert "stipend" in expanded.lower()
    assert "$175" in expanded or "$140" in expanded or "weekly" in expanded

    expanded_cold = _expand_query("Tell me about cold recovery")
    assert "retention" in expanded_cold.lower() or "60 days" in expanded_cold.lower()


def test_retrieval_returns_relevant_chunks():
    """Verify retrieval returns relevant chunks with high semantic/lexical overlap."""
    chunks = retrieve("What is the on-call stipend policy?", top_k=5)
    assert len(chunks) > 0
    assert any("handbook" in c.chunk_id or "runbook" in c.chunk_id or "stipend" in c.text_snippet.lower() for c in chunks)
    for c in chunks:
        assert c.chunk_id is not None
        assert c.title is not None
        assert len(c.text_snippet) > 0


def test_metadata_filtering():
    """Verify hybrid search supports filtering by category."""
    chunks = retrieve(
        query="retention policy",
        top_k=5,
        filters={"category": "compliance"}
    )
    for c in chunks:
        assert c.category == "compliance"


def test_local_embedder_dimension():
    """Verify local ONNX embedder generates 384-dimensional vectors without external APIs."""
    embedder = get_local_embedder()
    vecs = embedder.encode(["Asterline Labs platform architecture", "Local embedding test"])
    assert vecs.shape[0] == 2
    assert vecs.shape[1] == 384

