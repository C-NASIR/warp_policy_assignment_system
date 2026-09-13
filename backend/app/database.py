import os
from collections.abc import Generator, Mapping
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


# Keep local configuration beside the backend while allowing process-level
# environment variables to override every value in deployed environments.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


# Local Homebrew PostgreSQL installs create a role matching the macOS user and
# expose a Unix socket. Production and remote environments should set
# DATABASE_URL explicitly.
DEFAULT_DATABASE_URL = "postgresql+psycopg:///policy_assignments"
DEFAULT_DEMO_DATABASE_URL = "postgresql+psycopg:///policy_assignments_demo"
DATABASE_MODES = frozenset({"real", "demo"})


def database_url_for_mode(environment: Mapping[str, str] | None = None) -> str:
    """Select the real or demo connection without changing either URL."""
    values = environment if environment is not None else os.environ
    mode = values.get("DATABASE_MODE", "real").strip().lower()
    if mode not in DATABASE_MODES:
        raise RuntimeError("DATABASE_MODE must be either 'real' or 'demo'")
    if mode == "demo":
        return values.get("DEMO_DATABASE_URL", DEFAULT_DEMO_DATABASE_URL)
    return values.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def postgresql_url(value: str) -> URL:
    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must use PostgreSQL")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


DATABASE_MODE = os.getenv("DATABASE_MODE", "real").strip().lower()
DATABASE_URL = database_url_for_mode()
engine = create_engine(postgresql_url(DATABASE_URL), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def create_tables() -> None:
    from app import models  # noqa: F401
    from app.services.condition_fields import sync_condition_field_definitions

    Base.metadata.create_all(bind=engine)
    with SessionLocal.begin() as session:
        # Multiple Uvicorn processes may start together. Serialize the small
        # system-catalog upsert so the unique field keys remain race-free.
        session.execute(text("SELECT pg_advisory_xact_lock(762341908)"))
        sync_condition_field_definitions(session)
