"""Direct research and retrieval query endpoint."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.research_agent import ResearchAgent
from app.agents.verification_agent import VerificationAgent
from app.schemas.research import ChunkReference, ConflictInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])

research_agent = ResearchAgent()
verification_agent = VerificationAgent()


class ResearchQueryReq(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = 5
    filters: Optional[Dict[str, Any]] = None


class ResearchQueryResp(BaseModel):
    question: str
    chunks: List[ChunkReference]
    verified_chunks: List[ChunkReference]
    conflicts: List[ConflictInfo]
    uncertainty_level: str
    attempts_used: int
    quality_reason: str


@router.post("/query", response_model=ResearchQueryResp)
def direct_research_query(req: ResearchQueryReq):
    chunks, attempts, quality_reason = research_agent.retrieve_with_retries(
        question=req.question,
        filters=req.filters,
        top_k=req.top_k,
    )
    verification_res = verification_agent.verify(req.question, chunks)

    return ResearchQueryResp(
        question=req.question,
        chunks=chunks,
        verified_chunks=verification_res["verified_chunks"],
        conflicts=verification_res["conflicts"],
        uncertainty_level=verification_res["uncertainty_level"],
        attempts_used=attempts,
        quality_reason=quality_reason,
    )

