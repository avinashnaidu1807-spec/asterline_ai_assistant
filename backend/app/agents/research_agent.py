"""ResearchAgent: retrieval with quality checks and query reformulation."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.retrieval import retriever, reranking
from app.schemas.research import ChunkReference

logger = logging.getLogger(__name__)

_QUALITY_THRESHOLD = 0.15  # minimum RRF score to consider evidence adequate
_MIN_CHUNKS_ADEQUATE = 2


class ResearchAgent:
    """Performs hybrid retrieval with quality checks and up to 2 query reformulations."""

    def retrieve(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
    ) -> Tuple[List[ChunkReference], bool, str]:
        """
        Retrieve relevant chunks for the question.
        Returns (chunks, quality_ok, quality_reason).
        """
        k = top_k or settings.TOP_K_RETRIEVAL
        chunks = retriever.retrieve(question, top_k=k, filters=filters)
        chunks = reranking.rerank(question, chunks)
        quality_ok, reason = self._retrieval_quality_check(chunks)
        return chunks, quality_ok, reason

    def _reformulate_query(self, question: str, attempt: int) -> str:
        """Generate a broader reformulation of the query for retry."""
        # Simple keyword extraction strategy:
        # attempt 1 → drop stop words, use core nouns
        # attempt 2 → use first noun phrase only
        stop_words = {
            "what", "is", "the", "a", "an", "of", "in", "on", "at", "to", "for",
            "with", "by", "from", "and", "or", "not", "how", "why", "when", "where",
            "which", "who", "are", "was", "were", "be", "been", "being", "have", "has",
            "had", "do", "does", "did", "will", "would", "could", "should", "may", "might",
        }
        words = question.split()
        keywords = [w for w in words if w.lower() not in stop_words and len(w) > 2]
        if attempt == 1:
            return " ".join(keywords) if keywords else question
        else:
            # Even broader: just the first 3 meaningful keywords
            return " ".join(keywords[:3]) if keywords else question

    def retrieve_with_retries(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None,
        max_retries: int = 2,
    ) -> Tuple[List[ChunkReference], int, str]:
        """
        Full retrieval with up to max_retries additional attempts using reformulated queries.
        Returns (chunks, attempts_used, final_quality_reason).
        """
        chunks, quality_ok, reason = self.retrieve(question, filters, top_k)
        attempts = 1

        if quality_ok:
            return chunks, attempts, reason

        for attempt in range(1, max_retries + 1):
            if quality_ok:
                break
            reformulated = self._reformulate_query(question, attempt)
            logger.info(f"Retrieval attempt {attempt + 1}: reformulated query = '{reformulated}'")
            new_chunks, quality_ok, reason = self.retrieve(reformulated, filters, top_k)
            # Merge with existing chunks and deduplicate
            seen = {c.chunk_id for c in chunks}
            for c in new_chunks:
                if c.chunk_id not in seen:
                    chunks.append(c)
                    seen.add(c.chunk_id)
            attempts += 1

        return chunks[:top_k or settings.TOP_K_RETRIEVAL], attempts, reason

    def _retrieval_quality_check(self, chunks: List[ChunkReference]) -> Tuple[bool, str]:
        """Assess whether retrieved evidence is adequate."""
        if not chunks:
            return False, "No chunks retrieved"
        if len(chunks) < _MIN_CHUNKS_ADEQUATE:
            return False, f"Only {len(chunks)} chunk(s) retrieved, evidence may be insufficient"
        top_score = chunks[0].relevance_score if chunks else 0.0
        if top_score < _QUALITY_THRESHOLD:
            return False, f"Top relevance score {top_score:.3f} is below threshold {_QUALITY_THRESHOLD}"
        return True, f"Adequate evidence: {len(chunks)} chunks, top score {top_score:.3f}"
