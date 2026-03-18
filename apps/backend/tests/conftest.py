"""Shared pytest fixtures for backend API tests."""

from collections.abc import Generator
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("ALLOW_OPEN_REGISTRATION", "true")
os.environ.setdefault("RUN_RECONCILER_ENABLED", "false")

from app.core.db import get_db
from app.main import app
from app.models.base import Base


@pytest.fixture
def db_session_factory() -> Generator[sessionmaker[Session], None, None]:
    """Provide an isolated in-memory session factory for one test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

    Base.metadata.create_all(bind=engine)

    yield session_local

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session_factory: sessionmaker[Session]) -> Generator[TestClient, None, None]:
    """Provide API client with isolated in-memory SQLite DB."""

    def override_get_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as api_client:
        yield api_client

    app.dependency_overrides.clear()
