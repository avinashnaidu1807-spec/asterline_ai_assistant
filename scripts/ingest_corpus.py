#!/usr/bin/env python3
"""
Ingest the Asterline corpus into the local ChromaDB vector store.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_corpus")


def main():
    from app.config import settings
    from app.database.connection import init_db
    from app.retrieval.ingestion import run_ingestion, get_ingestion_status

    logger.info("Initializing database...")
    init_db()

    # Find corpus file
    corpus_candidates = [
        settings.CORPUS_PATH,
        "./data/corpus.jsonl",
        "../data/corpus.jsonl",
        "A:/repos/mint/data/corpus.jsonl",
        str(Path(__file__).resolve().parent.parent / "data" / "corpus.jsonl"),
        str(Path(__file__).resolve().parent.parent / "backend" / "data" / "corpus.jsonl"),
    ]
    for candidate in corpus_candidates:
        if Path(candidate).exists():
            settings.CORPUS_PATH = str(Path(candidate).resolve())
            logger.info(f"Using corpus path: {settings.CORPUS_PATH}")
            break

    stats = run_ingestion()
    logger.info(f"Ingestion result: {stats}")

    status = get_ingestion_status()
    logger.info(f"Current collection status: {status}")


if __name__ == "__main__":
    main()
