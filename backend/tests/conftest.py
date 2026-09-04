import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://postgres:postgres@localhost:5432/"
    "policy_assignments_test"
)
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
test_database_url = make_url(TEST_DATABASE_URL)
if test_database_url.get_backend_name() != "postgresql":
    raise RuntimeError("TEST_DATABASE_URL must use a dedicated PostgreSQL database")
if test_database_url.drivername == "postgresql":
    test_database_url = test_database_url.set(drivername="postgresql+psycopg")

# The application engine is initialized at import time. Point it at the same
# dedicated database used by the test fixtures before importing the app.
os.environ["DATABASE_URL"] = test_database_url.render_as_string(hide_password=False)
TEST_BOOTSTRAP_TOKEN = "test-bootstrap-token-with-at-least-32-bytes"
os.environ["AUTH_BOOTSTRAP_TOKEN"] = TEST_BOOTSTRAP_TOKEN
os.environ["AUTH_BOOTSTRAP_SUBJECT"] = "api"
os.environ["AUTH_MFA_ENCRYPTION_KEY"] = "test-mfa-encryption-key-at-least-32-bytes"
# Existing feature tests focus on their own authorization boundary. Phase 7
# has dedicated tests that opt into privileged MFA enforcement explicitly.
os.environ["AUTH_REQUIRE_PRIVILEGED_MFA"] = "false"

from app import models  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.services.condition_fields import sync_condition_field_definitions


@pytest.fixture
def session_factory():
    engine = create_engine(test_database_url, poolclass=NullPool)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        sync_condition_field_definitions(session)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session_factory):
    def override_db():
        with session_factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        test_client.headers.update(
            {"Authorization": f"Bearer {TEST_BOOTSTRAP_TOKEN}"}
        )
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db(session_factory) -> Generator[Session, None, None]:
    with session_factory() as session:
        yield session
