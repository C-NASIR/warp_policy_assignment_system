import os
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://postgres:postgres@localhost:5432/policy_assignments"
)


def postgresql_url(value: str) -> URL:
    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError("DATABASE_URL must use PostgreSQL")
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    return url


DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
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
