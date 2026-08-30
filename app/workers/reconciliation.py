from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.database import engine
from app.dates import current_datetime
from app.services.scheduled_reconciliations import reconcile_due_events

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 50
DEFAULT_MAX_RUNTIME_SECONDS = 15 * 60
DEFAULT_ADVISORY_LOCK_KEY = 8_675_309_001


class ReconciliationWorkerConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReconciliationWorkerSettings:
    batch_size: int = DEFAULT_BATCH_SIZE
    max_runtime_seconds: int = DEFAULT_MAX_RUNTIME_SECONDS
    advisory_lock_key: int = DEFAULT_ADVISORY_LOCK_KEY

    @classmethod
    def from_environment(cls) -> ReconciliationWorkerSettings:
        return cls(
            batch_size=_positive_integer(
                "RECONCILIATION_BATCH_SIZE",
                DEFAULT_BATCH_SIZE,
            ),
            max_runtime_seconds=_positive_integer(
                "RECONCILIATION_MAX_RUNTIME_SECONDS",
                DEFAULT_MAX_RUNTIME_SECONDS,
            ),
            advisory_lock_key=_positive_integer(
                "RECONCILIATION_ADVISORY_LOCK_KEY",
                DEFAULT_ADVISORY_LOCK_KEY,
                maximum=2**63 - 1,
            ),
        )


@dataclass(frozen=True)
class ReconciliationWorkerResult:
    acquired_lock: bool
    drained: bool
    processed_events: int
    batches: int
    started_at: datetime
    completed_at: datetime

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()


def run_worker(
    *,
    database_engine: Engine = engine,
    settings: ReconciliationWorkerSettings | None = None,
    clock: Callable[[], datetime] = current_datetime,
    monotonic_clock: Callable[[], float] = monotonic,
) -> ReconciliationWorkerResult:
    """Run one PostgreSQL-only, singleton reconciliation worker invocation."""
    _require_postgresql(database_engine)
    settings = settings or ReconciliationWorkerSettings.from_environment()
    started_at = clock()

    with database_engine.connect() as connection:
        acquired_lock = bool(
            connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": settings.advisory_lock_key},
            )
        )
        connection.commit()
        if not acquired_lock:
            completed_at = clock()
            return ReconciliationWorkerResult(
                acquired_lock=False,
                drained=False,
                processed_events=0,
                batches=0,
                started_at=started_at,
                completed_at=completed_at,
            )

        try:
            with Session(bind=connection, expire_on_commit=False) as session:
                return _drain_due_reconciliations(
                    session,
                    settings=settings,
                    started_at=started_at,
                    clock=clock,
                    monotonic_clock=monotonic_clock,
                )
        finally:
            if connection.in_transaction():
                connection.rollback()
            connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": settings.advisory_lock_key},
            )
            connection.commit()


def _drain_due_reconciliations(
    session: Session,
    *,
    settings: ReconciliationWorkerSettings,
    started_at: datetime,
    clock: Callable[[], datetime],
    monotonic_clock: Callable[[], float],
) -> ReconciliationWorkerResult:
    started_monotonic = monotonic_clock()
    processed_events = 0
    batches = 0
    drained = False

    while True:
        if (
            batches > 0
            and monotonic_clock() - started_monotonic
            >= settings.max_runtime_seconds
        ):
            break

        processing_at = clock()
        with session.begin():
            events = reconcile_due_events(
                session,
                as_of=processing_at,
                limit=settings.batch_size,
            )

        if not events:
            drained = True
            break

        batches += 1
        processed_events += len(events)
        logger.info(
            "Processed scheduled reconciliation batch: batch=%d events=%d total=%d",
            batches,
            len(events),
            processed_events,
        )
        if len(events) < settings.batch_size:
            drained = True
            break

    return ReconciliationWorkerResult(
        acquired_lock=True,
        drained=drained,
        processed_events=processed_events,
        batches=batches,
        started_at=started_at,
        completed_at=clock(),
    )


def _require_postgresql(database_engine: Engine) -> None:
    if database_engine.dialect.name != "postgresql":
        raise ReconciliationWorkerConfigurationError(
            "The reconciliation worker requires a PostgreSQL DATABASE_URL"
        )


def _positive_integer(
    name: str,
    default: int,
    *,
    maximum: int | None = None,
) -> int:
    raw_value = os.getenv(name)
    try:
        value = int(raw_value) if raw_value is not None else default
    except ValueError as exc:
        raise ReconciliationWorkerConfigurationError(
            f"{name} must be a positive integer"
        ) from exc
    if value <= 0 or (maximum is not None and value > maximum):
        raise ReconciliationWorkerConfigurationError(
            f"{name} must be a positive integer"
        )
    return value


def main() -> int:
    try:
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        result = run_worker()
    except Exception:
        logger.exception("Scheduled reconciliation worker failed")
        return 1

    if not result.acquired_lock:
        logger.info("Another reconciliation worker owns the advisory lock; exiting")
        return 0

    logger.info(
        "Scheduled reconciliation worker completed: events=%d batches=%d "
        "drained=%s duration_seconds=%.3f",
        result.processed_events,
        result.batches,
        result.drained,
        result.duration_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
