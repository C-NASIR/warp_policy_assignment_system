#!/bin/sh

# Demo-only scheduler for Compose. Production deployments should invoke the
# one-shot `python -m app.workers.reconciliation` command with their platform's
# scheduler instead of running this loop.

set -u

interval="${POLICYOS_RECONCILIATION_INTERVAL_SECONDS:-60}"
case "$interval" in
  ''|*[!0-9]*|0)
    echo "POLICYOS_RECONCILIATION_INTERVAL_SECONDS must be a positive integer" >&2
    exit 2
    ;;
esac

stop_requested=0
child_pid=""

stop_scheduler() {
  stop_requested=1
  if [ -n "$child_pid" ]; then
    kill "$child_pid" 2>/dev/null || true
  fi
}

trap stop_scheduler INT TERM

echo "Starting demo reconciliation scheduler (interval=${interval}s)"
while [ "$stop_requested" -eq 0 ]; do
  python -m app.workers.reconciliation &
  child_pid=$!
  wait "$child_pid"
  worker_status=$?
  child_pid=""

  if [ "$stop_requested" -ne 0 ]; then
    break
  fi
  if [ "$worker_status" -ne 0 ]; then
    echo "Reconciliation invocation failed with status $worker_status" >&2
    exit "$worker_status"
  fi

  sleep "$interval" &
  child_pid=$!
  wait "$child_pid" || true
  child_pid=""
done

echo "Demo reconciliation scheduler stopped"
