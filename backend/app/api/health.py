"""Health and configuration status endpoint."""
from __future__ import annotations

import os
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.retrieval.ingestion import get_ingestion_status
from app.schemas.user import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    # 1. Database check
    db_status = "error"
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    # 2. Vector store check
    ingestion_info = get_ingestion_status()
    chunk_count = ingestion_info.get("chunk_count", 0)
    vs_status = f"connected ({chunk_count} chunks)" if ingestion_info.get("status") == "ready" else "error"

    # 3. LLM provider
    llm_status = f"{settings.LLM_PROVIDER} (model: {settings.OPENAI_MODEL if settings.LLM_PROVIDER == 'openai' else settings.OLLAMA_MODEL if settings.LLM_PROVIDER == 'ollama' else 'deterministic rule-based'})"

    # 4. LangSmith tracing
    tracing_enabled = os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() == "true" and bool(settings.LANGSMITH_API_KEY)
    langsmith_status = f"enabled (project: {settings.LANGSMITH_PROJECT})" if tracing_enabled else "disabled (credentials not configured)"

    return HealthResponse(
        status="ok" if db_status == "connected" and "connected" in vs_status else "degraded",
        database=db_status,
        vector_store=vs_status,
        llm=llm_status,
        ingestion="ready" if chunk_count >= 75 else f"incomplete ({chunk_count}/75 chunks)",
        langsmith=langsmith_status,
    )

