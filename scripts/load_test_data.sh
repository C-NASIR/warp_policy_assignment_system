#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_DATABASE_NAME="policy_assignments_demo"
DEFAULT_DATABASE_URL="postgresql+psycopg:///${DEFAULT_DATABASE_NAME}"

database_url="${DEMO_DATABASE_URL:-$DEFAULT_DATABASE_URL}"
reference_date=""
custom_database=false

if [[ -n "${DEMO_DATABASE_URL:-}" ]]; then
  custom_database=true
fi

usage() {
  cat <<'EOF'
Load the fictional Cedar Harbor Wind Systems test data.

Usage:
  ./scripts/load_test_data.sh [options]

Options:
  --database-url URL       Use a specific existing PostgreSQL database.
  --reference-date DATE    Anchor relative dates to YYYY-MM-DD.
  -h, --help               Show this help.

With no options, the script creates policy_assignments_demo when needed and
loads it. DEMO_DATABASE_URL can also select an existing demo database.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --database-url)
      if [[ $# -lt 2 ]]; then
        echo "Error: --database-url requires a value." >&2
        exit 2
      fi
      database_url="$2"
      custom_database=true
      shift 2
      ;;
    --reference-date)
      if [[ $# -lt 2 ]]; then
        echo "Error: --reference-date requires a YYYY-MM-DD value." >&2
        exit 2
      fi
      reference_date="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option '$1'." >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "Error: uv is required but was not found in PATH." >&2
  exit 1
fi

if [[ "$custom_database" == false ]]; then
  if ! command -v psql >/dev/null 2>&1 || ! command -v createdb >/dev/null 2>&1; then
    echo "Error: PostgreSQL's psql and createdb commands are required." >&2
    exit 1
  fi

  database_exists="$(psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${DEFAULT_DATABASE_NAME}'")"
  if [[ "$database_exists" != "1" ]]; then
    echo "Creating disposable PostgreSQL database ${DEFAULT_DATABASE_NAME}..."
    createdb "$DEFAULT_DATABASE_NAME"
  fi
fi

seed_arguments=()
if [[ -n "$reference_date" ]]; then
  seed_arguments+=(--reference-date "$reference_date")
fi

echo "Loading Cedar Harbor Wind Systems test data..."
cd "$REPOSITORY_ROOT/backend"
DATABASE_MODE=real DATABASE_URL="$database_url" uv run alembic upgrade head
DATABASE_MODE=real DATABASE_URL="$database_url" uv run python -m scripts.seed_demo_company "${seed_arguments[@]}"

echo
echo "Test data is ready."
echo "Set DATABASE_MODE=demo in backend/.env to run the API against it."
echo "Company guide: ${REPOSITORY_ROOT}/docs/seed-data-company.md"
echo "Login credentials: ${REPOSITORY_ROOT}/docs/seed-data-credentials.txt"
