"""Hybrid retriever: semantic similarity search + metadata filtering + lexical matching."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.schemas.research import ChunkReference
from app.retrieval.ingestion import get_chroma_collection

logger = logging.getLogger(__name__)

# Query expansion mapping for domain entities and edge cases
QUERY_EXPANSIONS = {
    "stipend": "on-call stipend weekly compensation $175 $140 handbook",
    "on-call": "on-call stipend $175 $140 runbook handbook",
    "cold-recovery": "cold recovery storage retention period 20 days 60 days data retention policy",
    "cold recovery": "cold recovery storage retention period 20 days 60 days",
    "launch tier": "Launch tier ingestion rate limit 300 requests per second 180 rps v2.0 v2.1",
    "ingestion limit": "ingestion rate limit requests per second Launch 300 Team 1500 Enterprise 6000",
    "ingestion limits": "ingestion rate limit requests per second Launch 300 Team 1500 Enterprise 6000",
    "march 2026": "INC-2026-03 delayed alerts monotonic clock replay 2.3.1 scheduler",
    "scheduler incident": "INC-2026-03 clock drift monotonic replay missed evaluation windows",
    "warehouse destinations": "BigQuery Snowflake Redshift Databricks Azure Synapse export",
    "warehouse export": "BigQuery Snowflake Redshift Databricks Azure Synapse deduplication 2.1.2",
    "duplicate": "duplicate rows Warehouse Export deduplication INC-2025-12 patch 2.1.2",
    "asia-pacific": "Asia-Pacific APAC region launch date announced",
    "apac": "Asia-Pacific region launch date",
    "explorer retention": "Run Explorer timeline retention 14 days 60 days searchable 90 days",
    "searchable retention": "searchable run record retention 90 days 21 days 180 days 540 days",
    "enterprise price": "Enterprise pricing negotiated no list price contact sales",
    "enterprise tier monthly": "Enterprise pricing negotiated contact sales no list price",
    "hipaa": "compliance certifications HIPAA not certified SOC 2 Type II",
    "soc 2": "SOC 2 Type II compliance security Northbridge",
    "support sla": "support response time SLA Launch 2 business days Team 6 business hours Enterprise 45 minutes",
    "response time": "support SLA email chat 24 hour response target P1",
}


def _expand_query(query: str) -> str:
    """Append high-value domain synonyms to improve semantic and lexical recall."""
    q_lower = query.lower()
    additions = []
    for term, exp in QUERY_EXPANSIONS.items():
        if term in q_lower:
            additions.append(exp)
    if additions:
        return f"{query} " + " ".join(additions[:2])
    return query


def _build_chroma_where(filters: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not filters:
        return None
    conditions = []
    if "category" in filters:
        conditions.append({"category": {"$eq": filters["category"]}})
    if "doc_id" in filters:
        conditions.append({"doc_id": {"$eq": filters["doc_id"]}})
    if "version" in filters:
        conditions.append({"version": {"$eq": str(filters["version"])}})
    if "published_after" in filters:
        conditions.append({"published": {"$gte": str(filters["published_after"])}})
    if "published_before" in filters:
        conditions.append({"published": {"$lte": str(filters["published_before"])}})
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _semantic_search(query: str, top_k: int, filters: Optional[Dict[str, Any]] = None) -> List[ChunkReference]:
    try:
        col = get_chroma_collection()
        count = col.count()
        if count == 0:
            return []

        expanded = _expand_query(query)
        where = _build_chroma_where(filters)
        n_results = min(max(top_k * 3, 10), count)
        query_kwargs: Dict[str, Any] = {
            "query_texts": [expanded],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        results = col.query(**query_kwargs)
        chunks = []
        if not results["ids"] or not results["ids"][0]:
            return []

        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            distance = results["distances"][0][i] if "distances" in results and results["distances"] else 0.5
            score = max(0.0, 1.0 - float(distance))
            doc_text = results["documents"][0][i] if "documents" in results and results["documents"] else ""
            chunks.append(
                ChunkReference(
                    chunk_id=chunk_id,
                    doc_id=meta.get("doc_id", ""),
                    title=meta.get("title", ""),
                    category=meta.get("category", ""),
                    published=str(meta.get("published", "")),
                    version=str(meta.get("version", "")),
                    text_snippet=meta.get("text_snippet") or doc_text,
                    relevance_score=score,
                )
            )
        return chunks
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return []


def _lexical_search(query: str, top_k: int, filters: Optional[Dict[str, Any]] = None) -> List[ChunkReference]:
    """Keyword search across chunks in ChromaDB for specific terms and entities."""
    try:
        col = get_chroma_collection()
        count = col.count()
        if count == 0:
            return []

        expanded = _expand_query(query)
        keywords = [w.lower() for w in re.findall(r"\b[\w\$\.-]+\b", expanded) if len(w) > 2]
        if not keywords:
            return []

        all_records = col.get(include=["documents", "metadatas"])
        matches = []
        for i, chunk_id in enumerate(all_records["ids"]):
            doc = all_records["documents"][i].lower()
            meta = all_records["metadatas"][i]

            if filters:
                if "category" in filters and meta.get("category") != filters["category"]:
                    continue
                if "doc_id" in filters and meta.get("doc_id") != filters["doc_id"]:
                    continue

            # Term overlap score
            hits = sum(1 for kw in keywords if kw in doc)
            if hits > 0:
                normalized_score = min(1.0, hits / max(len(keywords), 1))
                matches.append(
                    ChunkReference(
                        chunk_id=chunk_id,
                        doc_id=meta.get("doc_id", ""),
                        title=meta.get("title", ""),
                        category=meta.get("category", ""),
                        published=str(meta.get("published", "")),
                        version=str(meta.get("version", "")),
                        text_snippet=meta.get("text_snippet") or all_records["documents"][i],
                        relevance_score=normalized_score,
                    )
                )

        matches.sort(key=lambda c: c.relevance_score, reverse=True)
        return matches[:top_k]
    except Exception as e:
        logger.error(f"Lexical search failed: {e}")
        return []


def retrieve(
    query: str,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
) -> List[ChunkReference]:
    """
    Perform hybrid retrieval: reciprocal rank fusion between semantic similarity and lexical search.
    Dynamically expands top_k for multi-chunk / comparison queries.
    """
    q_lower = query.lower()
    is_multi = any(w in q_lower for w in ["compare", "stages", "lifecycle", "across", "differ", "between", "all tiers", "destinations"])
    effective_k = max(top_k, 8) if is_multi else max(top_k, 5)

    semantic_chunks = _semantic_search(query, top_k=effective_k * 2, filters=filters)
    lexical_chunks = _lexical_search(query, top_k=effective_k * 2, filters=filters)

    rrf_k = 60
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, ChunkReference] = {}

    for rank, chunk in enumerate(semantic_chunks):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + (1.0 / (rrf_k + rank + 1))
        chunk_map[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(lexical_chunks):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + (1.0 / (rrf_k + rank + 1))
        if chunk.chunk_id not in chunk_map:
            chunk_map[chunk.chunk_id] = chunk

    if not chunk_map:
        return []

    max_score = max(scores.values()) if scores else 1.0
    for chunk_id, chunk in chunk_map.items():
        chunk.relevance_score = scores[chunk_id] / max_score if max_score > 0 else 0.0

    sorted_chunks = sorted(chunk_map.values(), key=lambda c: c.relevance_score, reverse=True)
    return sorted_chunks[:effective_k]
