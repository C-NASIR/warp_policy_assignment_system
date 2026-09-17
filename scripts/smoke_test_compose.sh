#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "${script_dir}/.." && pwd)"
cd "$repository_root"

diagnostics() {
  status=$?
  if [[ "$status" -ne 0 ]]; then
    echo >&2
    echo "Compose smoke test failed. Current service state:" >&2
    docker compose ps -a >&2 || true
    echo >&2
    echo "Recent service logs:" >&2
    docker compose logs --no-color --tail=80 postgres init backend frontend reconciliation-worker mcp >&2 || true
  fi
  exit "$status"
}
trap diagnostics EXIT

container_id() {
  docker compose ps -a -q "$1"
}

assert_running() {
  local service="$1" id state
  id="$(container_id "$service")"
  [[ -n "$id" ]] || { echo "No container found for $service" >&2; return 1; }
  state="$(docker inspect --format '{{.State.Status}}' "$id")"
  [[ "$state" == "running" ]] || { echo "$service is $state, not running" >&2; return 1; }
}

assert_healthy() {
  local service="$1" id health
  id="$(container_id "$service")"
  [[ -n "$id" ]] || { echo "No container found for $service" >&2; return 1; }
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$id")"
  [[ "$health" == "healthy" ]] || { echo "$service health is $health" >&2; return 1; }
}

wait_for_health() {
  local service="$1" attempt
  for attempt in {1..60}; do
    if assert_healthy "$service" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "$service did not become healthy within 120 seconds" >&2
  assert_healthy "$service"
}

wait_for_init() {
  local attempt id state
  for attempt in {1..60}; do
    id="$(container_id init)"
    if [[ -n "$id" ]]; then
      state="$(docker inspect --format '{{.State.Status}}' "$id")"
      [[ "$state" == "exited" ]] && return 0
    fi
    sleep 2
  done
  echo "init did not finish within 120 seconds" >&2
  return 1
}

echo "Checking Compose configuration..."
docker compose config --quiet

echo "Checking container states and health..."
wait_for_health postgres
wait_for_init
wait_for_health backend
wait_for_health frontend
wait_for_health reconciliation-worker
wait_for_health mcp

init_id="$(container_id init)"
[[ -n "$init_id" ]] || { echo "No init container found" >&2; exit 1; }
[[ "$(docker inspect --format '{{.State.Status}}' "$init_id")" == "exited" ]] \
  || { echo "init has not exited" >&2; exit 1; }
[[ "$(docker inspect --format '{{.State.ExitCode}}' "$init_id")" == "0" ]] \
  || { echo "init did not complete successfully" >&2; exit 1; }

echo "Checking Alembic head and public service endpoints..."
docker compose exec -T backend python -c \
  'from app.database import require_current_schema; require_current_schema(); print("Alembic schema is at head")'
docker compose exec -T backend python -c \
  'import urllib.request; assert urllib.request.urlopen("http://127.0.0.1:8000/", timeout=5).status == 200; assert urllib.request.urlopen("http://127.0.0.1:8000/docs", timeout=5).status == 200'
docker compose exec -T frontend node -e \
  'Promise.all([fetch("http://127.0.0.1:3000/"), fetch("http://127.0.0.1:3000/login")]).then(rs => { if (rs.some(r => !r.ok)) process.exit(1) }).catch(() => process.exit(1))'
docker compose exec -T mcp python -c \
  'import json, urllib.request; data=json.load(urllib.request.urlopen("http://127.0.0.1:8001/.well-known/oauth-protected-resource/mcp", timeout=5)); assert data["resource"] == "http://localhost:8001/mcp"'

seed_counts() {
  docker compose exec -T backend python - <<'PY'
import urllib.request

token = "wpa_seed_cedar_harbor_readonly_2026_example_token"
counts = []
for path in ("employees", "policies"):
    request = urllib.request.Request(
        f"http://127.0.0.1:8000/{path}?limit=1",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.status == 200
        count = int(response.headers["X-Total-Count"])
        assert count > 0, f"seeded {path} are missing"
        counts.append(str(count))
print(":".join(counts))
PY
}

echo "Checking authenticated Cedar Harbor data..."
counts_before="$(seed_counts)"

echo "Re-running migration and seed initialization to verify idempotency..."
docker compose run --rm --no-deps init
counts_after="$(seed_counts)"
[[ "$counts_before" == "$counts_after" ]] \
  || { echo "Seed counts changed: $counts_before -> $counts_after" >&2; exit 1; }

assert_running reconciliation-worker
echo "Compose smoke test passed (employees: ${counts_after%%:*}, policies: ${counts_after##*:})."
