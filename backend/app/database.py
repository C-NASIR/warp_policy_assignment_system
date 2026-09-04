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
        # create_all does not add columns to an existing installation. Preserve
        # the global access of pre-Phase-3 roles, then make new roles default to
        # no employee rows until their scope is chosen explicitly.
        session.execute(
            text(
                "ALTER TABLE roles ADD COLUMN IF NOT EXISTS employee_scope "
                "VARCHAR(30) NOT NULL DEFAULT 'all'"
            )
        )
        session.execute(
            text(
                "ALTER TABLE roles ALTER COLUMN employee_scope SET DEFAULT 'none'"
            )
        )
        # Existing roles previously had access to every assignment domain.
        session.execute(
            text(
                "ALTER TABLE roles ADD COLUMN IF NOT EXISTS assignment_field_scope "
                "VARCHAR(20) NOT NULL DEFAULT 'all'"
            )
        )
        session.execute(
            text(
                "ALTER TABLE roles ALTER COLUMN assignment_field_scope "
                "SET DEFAULT 'none'"
            )
        )
        session.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
                "WHERE conname = 'ck_role_employee_scope' "
                "AND conrelid = 'roles'::regclass) THEN "
                "ALTER TABLE roles ADD CONSTRAINT ck_role_employee_scope "
                "CHECK (employee_scope IN "
                "('all', 'reporting_tree', 'self', 'none')); "
                "END IF; END $$"
            )
        )
        session.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
                "WHERE conname = 'ck_role_assignment_field_scope' "
                "AND conrelid = 'roles'::regclass) THEN "
                "ALTER TABLE roles ADD CONSTRAINT ck_role_assignment_field_scope "
                "CHECK (assignment_field_scope IN ('all', 'selected', 'none')); "
                "END IF; END $$"
            )
        )
        sync_condition_field_definitions(session)
