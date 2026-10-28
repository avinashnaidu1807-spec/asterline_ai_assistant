"""FastAPI main application for Asterline Research Assistant."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, conversations, health, memories, research, users
from app.config import settings
from app.database.connection import init_db
from app.retrieval.ingestion import run_ingestion

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("asterline_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Asterline Research Assistant backend...")
    init_db()
    logger.info("Database initialized.")

    try:
        stats = run_ingestion()
        logger.info(f"Ingestion verified: {stats.get('status')}")
    except Exception as e:
        logger.warning(f"Corpus ingestion during startup notice: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Asterline Research Assistant backend...")


app = FastAPI(
    title=settings.APP_TITLE,
    description="Multi-agent research assistant for Asterline Labs with persistent memory and LangSmith observability.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers under /api
app.include_router(users.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(memories.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(research.router, prefix="/api")
app.include_router(health.router, prefix="/api")

# Also mount root health check
app.include_router(health.router)


@app.get("/")
def root():
    return {
        "app": settings.APP_TITLE,
        "status": "online",
        "docs_url": "/docs",
        "health_url": "/api/health",
    }
