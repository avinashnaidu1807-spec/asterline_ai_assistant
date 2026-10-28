"""SQLAlchemy engine setup and session management."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.database.models import Base, User

logger = logging.getLogger(__name__)

# Normalize DATABASE_URL for sync sqlite
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite+aiosqlite:///"):
    db_url = db_url.replace("sqlite+aiosqlite:///", "sqlite:///")

# Ensure data directory exists
os.makedirs("./data", exist_ok=True)
os.makedirs(os.path.dirname(db_url.replace("sqlite:///", "")) or ".", exist_ok=True)

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
    echo=settings.DEBUG,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Async-compatible alias for existing code
AsyncSessionLocal = SessionLocal


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables and seed default synthetic users."""
    import uuid
    from datetime import datetime

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")

    # Seed synthetic users
    seed_users = [
        {"username": "alice_chen", "display_name": "Alice Chen"},
        {"username": "bob_kumar", "display_name": "Bob Kumar"},
        {"username": "carol_reyes", "display_name": "Carol Reyes"},
    ]

    with SessionLocal() as session:
        for user_data in seed_users:
            result = session.execute(
                select(User).where(User.username == user_data["username"])
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                user = User(
                    id=str(uuid.uuid4()),
                    username=user_data["username"],
                    display_name=user_data["display_name"],
                    created_at=datetime.utcnow(),
                    is_active=True,
                )
                session.add(user)
                logger.info(f"Seeded user: {user_data['username']}")
        session.commit()
    logger.info("Database seeding complete.")
