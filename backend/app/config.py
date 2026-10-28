"""Application configuration using pydantic-settings."""
from __future__ import annotations

from typing import List, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM Provider
    LLM_PROVIDER: Literal["openai", "ollama", "mock"] = "mock"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"

    # LangSmith
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "asterline-research-assistant"
    LANGCHAIN_TRACING_V2: str = "false"

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Storage
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/asterline.db"
    CORPUS_PATH: str = "./data/corpus.jsonl"

    # Retrieval
    TOP_K_RETRIEVAL: int = 5
    MAX_RETRIES: int = 3

    # App
    DEBUG: bool = False
    APP_TITLE: str = "Asterline Research Assistant"
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )


settings = Settings()
