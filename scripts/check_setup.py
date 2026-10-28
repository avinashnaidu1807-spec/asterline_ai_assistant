#!/usr/bin/env python3
"""
Environment and system health verification script for Asterline Research Assistant.
Checks Python version, dependencies, SQLite database, ChromaDB vector store,
local embedder, and optional external integrations (OpenAI / LangSmith).
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

def main():
    print("=" * 65)
    print(" Asterline Assistant — Environment & Dependency Check")
    print("=" * 65)

    all_ok = True

    # 1. Python check
    py_ver = sys.version_info
    print(f"\n[1/6] Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    if py_ver.major < 3 or (py_ver.major == 3 and py_ver.minor < 10):
        print("  [FAIL] Python 3.10+ required.")
        all_ok = False
    else:
        print("  [OK] Supported Python version.")

    # 2. Package imports
    print("\n[2/6] Verifying Backend Dependencies:")
    pkgs = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("langgraph", "LangGraph"),
        ("pydantic", "Pydantic v2"),
        ("sqlalchemy", "SQLAlchemy"),
        ("chromadb", "ChromaDB"),
        ("onnxruntime", "ONNX Runtime"),
    ]
    for mod, name in pkgs:
        try:
            __import__(mod)
            print(f"  [OK] {name} installed.")
        except ImportError as e:
            print(f"  [FAIL] {name} missing: {e}")
            all_ok = False

    # 3. Database check
    print("\n[3/6] Verifying SQLite Database & Synthetic Users:")
    try:
        from app.database.connection import get_db_context, init_db
        from app.database.models import User
        from sqlalchemy import select
        init_db()
        with get_db_context() as session:
            users = session.execute(select(User)).scalars().all()
            print(f"  [OK] Database connected. Found {len(users)} seeded user(s): {[u.username for u in users]}")
    except Exception as e:
        print(f"  [FAIL] Database error: {e}")
        all_ok = False

    # 4. Local Embedder check
    print("\n[4/6] Verifying Local ONNX Embedder:")
    try:
        from app.retrieval.embedder import get_local_embedder
        embedder = get_local_embedder()
        vec = embedder.encode(["Test embedding vector"])
        print(f"  [OK] Local embedder operational. Shape: {vec.shape} (384-dimensional).")
    except Exception as e:
        print(f"  [FAIL] Embedder error: {e}")
        all_ok = False

    # 5. ChromaDB collection check
    print("\n[5/6] Verifying Vector Store Corpus:")
    try:
        from app.retrieval.ingestion import get_chroma_collection
        col = get_chroma_collection()
        cnt = col.count()
        if cnt == 75:
            print(f"  [OK] ChromaDB collection loaded with exactly {cnt}/75 chunks.")
        else:
            print(f"  [WARN] ChromaDB count is {cnt} (expected 75). Run scripts/ingest_corpus.py to sync.")
    except Exception as e:
        print(f"  [FAIL] ChromaDB error: {e}")
        all_ok = False

    # 6. Integrations & Tracing
    print("\n[6/6] Checking Optional Services:")
    from app.config import settings
    print(f"  • LLM Provider: {settings.LLM_PROVIDER}")
    if settings.LLM_PROVIDER == "openai":
        print(f"    OpenAI API Key: {'Configured' if settings.OPENAI_API_KEY else 'Missing'}")
    if settings.LANGSMITH_API_KEY:
        print(f"  • LangSmith Tracing: ENABLED (Project: {settings.LANGSMITH_PROJECT})")
    else:
        print(f"  • LangSmith Tracing: Not configured (optional for offline testing)")

    print("\n" + "=" * 65)
    if all_ok:
        print(" All core system checks passed! Ready to run.")
    else:
        print(" Some checks failed. Please address the errors above.")
    print("=" * 65)


if __name__ == "__main__":
    main()
