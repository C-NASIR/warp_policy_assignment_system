from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.workers import reconciliation as worker


def _settings(*, batch_size=2, max_runtime_seconds=60):
    return worker.ReconciliationWorkerSettings(
        batch_size=batch_size,
        max_runtime_seconds=max_runtime_seconds,
        advisory_lock_key=12345,
    )


def test_worker_settings_load_and_validate_environment(monkeypatch):
    monkeypatch.setenv("RECONCILIATION_BATCH_SIZE", "25")
    monkeypatch.setenv("RECONCILIATION_MAX_RUNTIME_SECONDS", "300")
    monkeypatch.setenv("RECONCILIATION_ADVISORY_LOCK_KEY", "999")

    assert worker.ReconciliationWorkerSettings.from_environment() == (
        worker.ReconciliationWorkerSettings(
            batch_size=25,
            max_runtime_seconds=300,
            advisory_lock_key=999,
        )
    )

    monkeypatch.setenv("RECONCILIATION_BATCH_SIZE", "0")
    with pytest.raises(
        worker.ReconciliationWorkerConfigurationError,
        match="RECONCILIATION_BATCH_SIZE must be a positive integer",
    ):
        worker.ReconciliationWorkerSettings.from_environment()


def test_worker_rejects_every_non_postgresql_engine():
    database_engine = SimpleNamespace(dialect=SimpleNamespace(name="unsupported"))

    with pytest.raises(
        worker.ReconciliationWorkerConfigurationError,
        match="requires a PostgreSQL DATABASE_URL",
    ):
        worker.run_worker(database_engine=database_engine)


def test_drain_processes_batches_until_a_partial_batch(monkeypatch):
    session = MagicMock()
    first_batch = [object(), object()]
    second_batch = [object()]
    reconcile = MagicMock(side_effect=[first_batch, second_batch])
    monkeypatch.setattr(worker, "reconcile_due_events", reconcile)
    started_at = datetime(2027, 1, 1, tzinfo=UTC)
    clock_values = iter(
        [
            started_at,
            started_at + timedelta(seconds=1),
            started_at + timedelta(seconds=2),
        ]
    )
    monotonic_values = iter([0.0, 1.0])

    result = worker._drain_due_reconciliations(
        session,
        settings=_settings(),
        started_at=started_at,
        clock=lambda: next(clock_values),
        monotonic_clock=lambda: next(monotonic_values),
    )

    assert result.acquired_lock is True
    assert result.drained is True
    assert result.processed_events == 3
    assert result.batches == 2
    assert result.completed_at == started_at + timedelta(seconds=2)
    assert session.begin.call_count == 2
    assert reconcile.call_count == 2
    assert all(call.kwargs["limit"] == 2 for call in reconcile.call_args_list)


def test_drain_stops_after_runtime_budget_without_claiming_another_batch(monkeypatch):
    session = MagicMock()
    reconcile = MagicMock(return_value=[object(), object()])
    monkeypatch.setattr(worker, "reconcile_due_events", reconcile)
    started_at = datetime(2027, 1, 1, tzinfo=UTC)
    clock_values = iter([started_at, started_at + timedelta(seconds=11)])
    monotonic_values = iter([0.0, 11.0])

    result = worker._drain_due_reconciliations(
        session,
        settings=_settings(max_runtime_seconds=10),
        started_at=started_at,
        clock=lambda: next(clock_values),
        monotonic_clock=lambda: next(monotonic_values),
    )

    assert result.drained is False
    assert result.processed_events == 2
    assert result.batches == 1
    assert reconcile.call_count == 1


def test_run_exits_cleanly_when_another_worker_holds_the_advisory_lock():
    database_engine = MagicMock()
    database_engine.dialect.name = "postgresql"
    connection = database_engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = False
    started_at = datetime(2027, 1, 1, tzinfo=UTC)
    clock_values = iter([started_at, started_at + timedelta(seconds=1)])

    result = worker.run_worker(
        database_engine=database_engine,
        settings=_settings(),
        clock=lambda: next(clock_values),
    )

    assert result.acquired_lock is False
    assert result.processed_events == 0
    assert connection.commit.call_count == 1
    connection.execute.assert_not_called()


def test_run_releases_advisory_lock_when_processing_fails(monkeypatch):
    database_engine = MagicMock()
    database_engine.dialect.name = "postgresql"
    connection = database_engine.connect.return_value.__enter__.return_value
    connection.scalar.return_value = True
    connection.in_transaction.return_value = True
    session_context = MagicMock()
    monkeypatch.setattr(worker, "Session", MagicMock(return_value=session_context))
    monkeypatch.setattr(
        worker,
        "_drain_due_reconciliations",
        MagicMock(side_effect=RuntimeError("reconciliation failed")),
    )

    with pytest.raises(RuntimeError, match="reconciliation failed"):
        worker.run_worker(
            database_engine=database_engine,
            settings=_settings(),
        )

    connection.rollback.assert_called_once()
    assert "pg_advisory_unlock" in str(connection.execute.call_args.args[0])
    assert connection.commit.call_count == 2
