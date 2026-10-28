"""VerificationAgent: verifies chunks against the question, detects conflicts."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.research import ChunkReference, Claim, ConflictInfo

logger = logging.getLogger(__name__)

# Language patterns that explicitly indicate a document supersedes another
_SUPERSESSION_PATTERNS = [
    re.compile(r"(?i)supersede[sd]?\b"),
    re.compile(r"(?i)replace[sd]?\b"),
    re.compile(r"(?i)amend[sed]?\b"),
    re.compile(r"(?i)revoke[sd]?\b"),
    re.compile(r"(?i)nullif(?:ies|ied|y)\b"),
    re.compile(r"(?i)effective\s+(?:as\s+of|from|date)\s+"),
    re.compile(r"(?i)this\s+(?:document|policy|version)\s+(?:supersedes|replaces|amends)"),
    re.compile(r"(?i)overrides?\b"),
]

_EFFECTIVE_DATE_PATTERN = re.compile(
    r"(?i)effective\s+(?:as\s+of|from)?\s*(\d{4}[-/]\d{2}[-/]\d{2}|\w+\s+\d{1,2},?\s+\d{4})"
)


class VerificationAgent:
    """Verifies retrieved chunks against the question and detects conflicts."""

    def verify(
        self,
        question: str,
        chunks: List[ChunkReference],
    ) -> Dict[str, Any]:
        """
        Returns:
          verified_chunks: List[ChunkReference] - chunks that genuinely support an answer
          conflicts: List[ConflictInfo]
          uncertainty_level: "low" | "medium" | "high"
          reasoning: str
        """
        if not chunks:
            return {
                "verified_chunks": [],
                "conflicts": [],
                "uncertainty_level": "high",
                "reasoning": "No chunks were provided for verification.",
            }

        verified_chunks = self._filter_relevant(question, chunks)
        conflicts = self._detect_conflicts(verified_chunks)
        uncertainty_level = self._assess_uncertainty(verified_chunks, conflicts)

        reasoning_parts = [
            f"Verified {len(verified_chunks)} of {len(chunks)} retrieved chunks as relevant.",
        ]
        if conflicts:
            reasoning_parts.append(f"Detected {len(conflicts)} conflict(s).")
        reasoning_parts.append(f"Uncertainty level: {uncertainty_level}.")

        return {
            "verified_chunks": verified_chunks,
            "conflicts": conflicts,
            "uncertainty_level": uncertainty_level,
            "reasoning": " ".join(reasoning_parts),
        }

    def _filter_relevant(
        self, question: str, chunks: List[ChunkReference]
    ) -> List[ChunkReference]:
        """Keep chunks that share meaningful keywords with the question."""
        from app.retrieval.retriever import _expand_query
        stop_words = {
            "what", "is", "the", "a", "an", "of", "in", "on", "at", "to", "for",
            "with", "by", "from", "and", "or", "how", "why", "when", "where", "which",
            "who", "are", "was", "were", "be", "has", "have", "had", "do", "does",
            "tell", "me", "about", "can", "you", "please", "full", "form",
        }
        expanded_q = _expand_query(question)
        question_words = {
            w.lower() for w in re.findall(r"\w+", expanded_q) if w.lower() not in stop_words and len(w) > 2
        }
        if not question_words:
            return []

        relevant = []
        for chunk in chunks:
            snippet_words = {
                w.lower() for w in re.findall(r"\w+", chunk.text_snippet)
            }
            overlap = question_words & snippet_words
            if overlap:
                relevant.append(chunk)

        return relevant

    def _detect_conflicts(self, chunks: List[ChunkReference]) -> List[ConflictInfo]:
        """
        Detect conflicts: same conceptual topic but different values across docs.
        Compares chunks from different doc_ids with overlapping keywords.
        """
        conflicts: List[ConflictInfo] = []
        checked_pairs: set = set()

        for i, chunk_a in enumerate(chunks):
            for j, chunk_b in enumerate(chunks):
                if j <= i:
                    continue
                pair_key = tuple(sorted([chunk_a.chunk_id, chunk_b.chunk_id]))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)

                # Only flag potential conflicts across different documents
                if chunk_a.doc_id == chunk_b.doc_id:
                    continue

                # Check for meaningful topic overlap
                words_a = set(re.findall(r"\w+", chunk_a.text_snippet.lower()))
                words_b = set(re.findall(r"\w+", chunk_b.text_snippet.lower()))
                stop_words = {"the", "a", "an", "is", "in", "of", "and", "or", "to", "for", "with", "by", "on"}
                common = words_a & words_b - stop_words
                has_supersession = self._check_supersession(chunk_a.text_snippet) or self._check_supersession(chunk_b.text_snippet)
                min_overlap = 2 if has_supersession else 3
                if len(common) < min_overlap:
                    continue  # not enough overlap to be a conflict

                # Check for contradicting numeric or categorical values
                nums_a = set(re.findall(r"\b\d+(?:\.\d+)?(?:%|days?|months?|years?|usd|\$)?\b", chunk_a.text_snippet.lower()))
                nums_b = set(re.findall(r"\b\d+(?:\.\d+)?(?:%|days?|months?|years?|usd|\$)?\b", chunk_b.text_snippet.lower()))

                if nums_a and nums_b and nums_a != nums_b:
                    resolution, resolution_reason = self._resolve_conflict(chunk_a, chunk_b)
                    conflicts.append(
                        ConflictInfo(
                            chunk_ids=[chunk_a.chunk_id, chunk_b.chunk_id],
                            conflicting_values=(
                                f"Doc '{chunk_a.doc_id}' (v{chunk_a.version}): {nums_a} | "
                                f"Doc '{chunk_b.doc_id}' (v{chunk_b.version}): {nums_b}"
                            ),
                            resolution=resolution,
                            resolution_reason=resolution_reason,
                        )
                    )

        return conflicts

    def _check_supersession(self, text: str) -> bool:
        """Check if text explicitly states supersession."""
        for pattern in _SUPERSESSION_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def _extract_effective_date(self, text: str) -> Optional[str]:
        """Extract explicit effective date from text."""
        match = _EFFECTIVE_DATE_PATTERN.search(text)
        return match.group(1) if match else None

    def _resolve_conflict(
        self, chunk_a: ChunkReference, chunk_b: ChunkReference
    ) -> Tuple[str, str]:
        """
        Resolve which chunk is authoritative.
        Priority: explicit supersession language > effective date > publication date > version.
        Never resolves solely by recency.
        """
        text_a = chunk_a.text_snippet
        text_b = chunk_b.text_snippet

        supersedes_a = self._check_supersession(text_a)
        supersedes_b = self._check_supersession(text_b)

        if supersedes_a and not supersedes_b:
            return chunk_a.chunk_id, "Chunk A contains explicit supersession language"
        if supersedes_b and not supersedes_a:
            return chunk_b.chunk_id, "Chunk B contains explicit supersession language"

        # Check effective dates
        eff_a = self._extract_effective_date(text_a)
        eff_b = self._extract_effective_date(text_b)
        if eff_a and eff_b:
            if eff_a > eff_b:
                return chunk_a.chunk_id, f"Chunk A has later effective date ({eff_a} vs {eff_b})"
            elif eff_b > eff_a:
                return chunk_b.chunk_id, f"Chunk B has later effective date ({eff_b} vs {eff_a})"

        # Use publication date if available
        pub_a = chunk_a.published or ""
        pub_b = chunk_b.published or ""
        if pub_a and pub_b and pub_a != pub_b:
            if pub_a > pub_b:
                return chunk_a.chunk_id, f"Chunk A has later publication date ({pub_a} vs {pub_b}); verify with effective dates"
            else:
                return chunk_b.chunk_id, f"Chunk B has later publication date ({pub_b} vs {pub_a}); verify with effective dates"

        # Try version comparison
        try:
            ver_a = tuple(int(x) for x in chunk_a.version.lstrip("v").split("."))
            ver_b = tuple(int(x) for x in chunk_b.version.lstrip("v").split("."))
            if ver_a > ver_b:
                return chunk_a.chunk_id, f"Chunk A has higher version ({chunk_a.version} vs {chunk_b.version})"
            elif ver_b > ver_a:
                return chunk_b.chunk_id, f"Chunk B has higher version ({chunk_b.version} vs {chunk_a.version})"
        except (ValueError, AttributeError):
            pass

        return "unresolved", "Cannot determine authoritative source without explicit supersession language or effective dates"

    def _assess_uncertainty(
        self, verified_chunks: List[ChunkReference], conflicts: List[ConflictInfo]
    ) -> str:
        if not verified_chunks:
            return "high"
        unresolved_conflicts = sum(1 for c in conflicts if c.resolution == "unresolved")
        if unresolved_conflicts > 0:
            return "high"
        if conflicts:
            return "medium"
        avg_score = sum(c.relevance_score for c in verified_chunks) / len(verified_chunks)
        if avg_score < 0.2:
            return "medium"
        return "low"
