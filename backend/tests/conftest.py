"""Pytest configuration and global fixtures."""
import pytest
from app.database.connection import init_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure database tables and synthetic seed users exist before tests run."""
    init_db()

