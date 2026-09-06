"""Populate a fresh testing database with the Cedar Harbor demo company."""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        help="PostgreSQL URL. Defaults to the database selected by DATABASE_MODE.",
    )
    parser.add_argument(
        "--reference-date",
        type=lambda value: datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC),
        help="Anchor relative seed dates to YYYY-MM-DD for reproducible tests.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.database_url:
        # An explicit target must not be redirected by DATABASE_MODE from .env.
        os.environ["DATABASE_MODE"] = "real"
        os.environ["DATABASE_URL"] = args.database_url

    from app.database import SessionLocal, create_tables
    from app.demo_seed import seed_demo_company

    create_tables()
    with SessionLocal.begin() as session:
        summary = seed_demo_company(session, reference_time=args.reference_date)

    print(f"Seeded {summary.company}.")
    print(
        f"{summary.employees} employees, {summary.users} users, {summary.roles} roles, "
        f"{summary.groups} groups, {summary.policies} policies, "
        f"{summary.assignments} assignment records, {summary.audit_logs} audit entries."
    )
    print("Test logins: ../docs/seed-data-credentials.txt")
    print("Company guide: ../docs/seed-data-company.md")


if __name__ == "__main__":
    main()
