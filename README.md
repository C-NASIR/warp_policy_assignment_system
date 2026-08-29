# Warp Policy Assignment System

Version 1 is a small FastAPI backend that answers: given an employee's current facts, which field values should be assigned to them now?

## Architecture

The application uses FastAPI and Pydantic at the API boundary, explicit application services for domain behavior, SQLAlchemy 2 for persistence, and SQLite as the local database. Database access is kept behind SQLAlchemy sessions, so a later PostgreSQL move primarily requires changing `DATABASE_URL` and adding migrations.

```text
Employee
→ Compiled Policy Matching
→ Employee Policies
→ Candidate Field Values
→ Conflict Resolution
→ Employee Assignments
```

Policy condition trees are compiled into flat OR-of-AND clauses. Employee reconciliation evaluates those clauses in SQL, persists matching policy links, and resolves each assignment field independently. The reconciliation service replaces persisted assignments with the desired result in the request transaction.

For cardinality `one`, the highest-priority policy wins. Equal-priority policies producing different values return HTTP 409 instead of selecting arbitrarily. For cardinality `many`, unique values are retained. If several policies produce the same many-valued result, its recorded source is the highest-priority policy, breaking remaining ties by lowest policy ID.

## Domain concepts

- **Employee:** current name, state, department, employee type, location, and start date.
- **Condition tree:** nested `and`/`or` expressions over employee fields using `=`, `<`, and `<=` comparisons.
- **Compiled policy clause:** one flat set of conditions that must all match.
- **Employee policy:** a persisted match between an employee and a policy.
- **Field definition:** a named assignment field with `one` or `many` cardinality.
- **Policy:** a priority-ranked condition tree with assignment values.
- **Policy field value:** one relationally stored consequence of a policy.
- **Employee assignment:** a resolved value and the policy that supplied it.

## Install and run

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are expected.

```bash
uv sync
uv run fastapi dev main.py
```

The API runs at <http://127.0.0.1:8000>; interactive documentation is at <http://127.0.0.1:8000/docs>. By default, data is stored in `policy_assignments.db`. Override it with a SQLAlchemy URL, for example `DATABASE_URL=sqlite:///./other.db`.

Run tests with:

```bash
uv run pytest
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Health check |
| POST / GET | `/employees` | Create or list employees |
| GET / PATCH | `/employees/{id}` | Read or update an employee |
| GET | `/employees/{id}/assignments` | Read resolved assignments |
| POST | `/employees/{id}/refresh` | Recompute matching policies and assignments |
| POST / GET | `/field-definitions` | Create or list field definitions |
| GET | `/field-definitions/{id}` | Read a field definition |
| POST / GET | `/policies` | Create policies with values or list them |
| GET / PATCH | `/policies/{id}` | Read or update a policy and its values |

Employee creation and update automatically recalculate that employee. Creating or changing policy configuration intentionally does not reconcile all employees; use the explicit employee reconciliation endpoint.

## Alice example

Create `pay_schedule` (`one`) and `application_access` (`many`). Create a priority-20 policy conditioned on California that produces `biweekly` and `payroll_app`, and a priority-10 policy conditioned on Engineering that produces `weekly` and `GitHub`. Creating Alice in California Engineering automatically resolves:

```text
pay_schedule = biweekly
application_access = payroll_app
application_access = GitHub
```

Patching Alice's state to Wisconsin removes the California policy match and automatically leaves `weekly` and `GitHub`. The integration tests exercise this exact lifecycle.

## Version 1 boundaries

Version 1 intentionally excludes a frontend, PostgreSQL, migrations, policy versions and effective dates, historical evaluation, overrides, automatic company-wide reconciliation, workers and queues, caching, audit logs, authentication/authorization, simulation, and complex explainability.
