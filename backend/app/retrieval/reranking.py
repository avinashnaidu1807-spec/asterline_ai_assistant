"""Reranker: boosts chunks using lexical overlap, keyword density, and supersession signals."""
from __future__ import annotations

import logging
import re
from typing import List

from app.schemas.research import ChunkReference

logger = logging.getLogger(__name__)


def rerank(query: str, chunks: List[ChunkReference]) -> List[ChunkReference]:
    """
    Rerank chunks using lexical overlap, exact phrase match, and recency/version weighting.
    Runs 100% locally with zero external DLL or PyTorch dependencies.
    """
    if not chunks:
        return chunks

    query_words = set(re.findall(r"\b[\w\$\.-]+\b", query.lower()))
    stopwords = {
        "what", "is", "the", "a", "an", "of", "in", "on", "at", "to", "for",
        "with", "by", "from", "and", "or", "are", "was", "were", "be", "been",
        "how", "does", "did", "will", "would", "can", "could", "tell", "me"
    }
    meaningful_words = query_words - stopwords

    reranked = []
    for chunk in chunks:
        snippet_lower = chunk.text_snippet.lower()
        title_lower = chunk.title.lower()

        # Base score from hybrid retrieval
        score = chunk.relevance_score

        # Meaningful word matches
        if meaningful_words:
            matches = sum(1 for w in meaningful_words if w in snippet_lower or w in title_lower)
            word_overlap = matches / len(meaningful_words)
            score = 0.6 * score + 0.4 * word_overlap

        # Supersession boost if asking about current behavior or policy
        q_lower = query.lower()
        if "current" in q_lower or "supersede" in q_lower or "governs" in q_lower:
            if "supersede" in snippet_lower or "effective" in snippet_lower:
                score += 0.15

        chunk.relevance_score = min(1.0, score)
        reranked.append(chunk)

    reranked.sort(key=lambda c: c.relevance_score, reverse=True)
    return reranked
