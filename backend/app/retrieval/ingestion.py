"""Corpus ingestion pipeline for ChromaDB."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import chromadb.utils.embedding_functions as ef
from app.config import settings

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"chunk_id", "doc_id", "title", "category", "owner", "source_url", "published", "version", "text"}

_chroma_client = None
_collection = None
_embedding_fn = None


def get_embedding_function():
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = ef.ONNXMiniLM_L6_V2()
    return _embedding_fn


def get_chroma_collection():
    global _chroma_client, _collection
    if _collection is None:
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        _collection = _chroma_client.get_or_create_collection(
            name="research_corpus",
            embedding_function=get_embedding_function(),
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def compute_checksum(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


def load_corpus(path: str) -> List[Dict[str, Any]]:
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Skipping invalid JSON on line {line_num}: {e}")
                continue
            missing = REQUIRED_FIELDS - set(record.keys())
            if missing:
                logger.warning(f"Skipping record on line {line_num}, missing fields: {missing}")
                continue
            records.append(record)
    return records


def get_stored_checksum() -> Optional[str]:
    try:
        from sqlalchemy import text
        from app.database.connection import SessionLocal
        with SessionLocal() as session:
            result = session.execute(
                text("SELECT checksum FROM ingestion_metadata ORDER BY ingested_at DESC LIMIT 1")
            )
            row = result.fetchone()
            return row[0] if row else None
    except Exception:
        return None


def store_ingestion_metadata(checksum: str, total: int, added: int) -> None:
    try:
        from sqlalchemy import text
        from app.database.connection import engine, SessionLocal
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ingestion_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    checksum TEXT NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    chunks_added INTEGER NOT NULL,
                    ingested_at TEXT NOT NULL
                )
            """))
        with SessionLocal() as session:
            session.execute(
                text("INSERT INTO ingestion_metadata (checksum, total_chunks, chunks_added, ingested_at) VALUES (:checksum, :total, :added, :ts)"),
                {"checksum": checksum, "total": total, "added": added, "ts": datetime.utcnow().isoformat()},
            )
            session.commit()
    except Exception as e:
        logger.warning(f"Failed to store ingestion metadata: {e}")


def run_ingestion(force: bool = False) -> Dict[str, Any]:
    """Run the ingestion pipeline. Reusable and non-duplicating."""
    corpus_path = settings.CORPUS_PATH
    if not Path(corpus_path).exists():
        candidates = [
            "./data/corpus.jsonl",
            "../data/corpus.jsonl",
            "A:/repos/mint/data/corpus.jsonl",
            str(Path(__file__).resolve().parent.parent.parent / "data" / "corpus.jsonl"),
            str(Path(__file__).resolve().parent.parent / "data" / "corpus.jsonl"),
        ]
        for c in candidates:
            if Path(c).exists():
                corpus_path = c
                break

    if not Path(corpus_path).exists():
        logger.warning(f"Corpus not found at {corpus_path}")
        return {"status": "skipped", "reason": "corpus not found", "corpus_path": corpus_path}

    checksum = compute_checksum(corpus_path)
    collection = get_chroma_collection()
    existing_count = collection.count()
    stored_checksum = get_stored_checksum()

    if not force and stored_checksum == checksum and existing_count >= 75:
        logger.info(f"Corpus already ingested ({existing_count} chunks). Skipping.")
        return {
            "status": "already_ingested",
            "checksum": checksum,
            "existing_chunks": existing_count,
        }

    records = load_corpus(corpus_path)
    all_ids = [r["chunk_id"] for r in records]
    existing_ids = set()
    try:
        res = collection.get(ids=all_ids, include=[])
        existing_ids = set(res["ids"])
    except Exception:
        pass

    new_records = [r for r in records if r["chunk_id"] not in existing_ids]

    if not new_records and existing_count > 0:
        store_ingestion_metadata(checksum, len(records), 0)
        return {
            "status": "up_to_date",
            "checksum": checksum,
            "total_records": len(records),
            "chunks_added": 0,
        }

    batch_size = 15
    added = 0
    for i in range(0, len(new_records), batch_size):
        batch = new_records[i : i + batch_size]
        ids = [r["chunk_id"] for r in batch]
        documents = [r["text"] for r in batch]
        metadatas = [
            {
                "doc_id": str(r["doc_id"]),
                "title": str(r["title"]),
                "category": str(r["category"]),
                "owner": str(r["owner"]),
                "source_url": str(r["source_url"]),
                "published": str(r["published"]),
                "version": str(r["version"]),
                "text_snippet": str(r["text"][:300]),
            }
            for r in batch
        ]
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        added += len(batch)

    store_ingestion_metadata(checksum, len(records), added)

    stats = {
        "status": "completed",
        "checksum": checksum,
        "total_records": len(records),
        "chunks_added": added,
        "total_chunks_in_store": collection.count(),
        "timestamp": datetime.utcnow().isoformat(),
    }
    return stats


def get_ingestion_status() -> Dict[str, Any]:
    try:
        col = get_chroma_collection()
        return {"status": "ready", "chunk_count": col.count()}
    except Exception as e:
        return {"status": "error", "error": str(e)}
