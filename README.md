# Warp Policy Assignment System

Version 1 is a small FastAPI backend that answers: given an employee's current facts, which field values should be assigned to them now?

## Architecture

The application uses FastAPI and Pydantic at the API boundary, explicit application services for domain behavior, SQLAlchemy 2 for persistence, and SQLite as the local database. Alembic is configured for future migrations once persistent environments require them. Database access is kept behind SQLAlchemy sessions, so a later PostgreSQL move primarily requires changing `DATABASE_URL`.

```text
Employee
→ Direct Compiled Policy Matching + Group Policies
→ Employee Policies
→ Candidate Field Values
→ Conflict Resolution
→ Employee Overrides
→ Employee Assignments
```

Policy condition trees are compiled into flat OR-of-AND clauses. Employee reconciliation evaluates those clauses in SQL, persists matching policy links, and resolves each assignment field independently. The reconciliation service replaces persisted assignments with the desired result in the request transaction.

Groups are explicit collections of employees. A group contributes its attached policies as candidates for every member; it does not produce assignments of its own. Direct matches and group-inherited policies are deduplicated and sent through the same policy engine, so priority and conflict behavior is identical regardless of where a policy came from.

For cardinality `one`, the highest-priority policy wins. Equal-priority policies producing different values return HTTP 409 instead of selecting arbitrarily. For cardinality `many`, unique values are retained. If several policies produce the same many-valued result, its recorded source is the highest-priority policy, breaking remaining ties by lowest policy ID.

Manual overrides are field values applied after normal policy resolution. If a field has overrides, all policy-derived values for that field are replaced by its override values. A `one` field accepts one override per employee; a `many` field accepts multiple unique override values. Overrides can also create an assignment when no policy supplies that field. They do not suppress policy conflicts, which remain configuration errors.

## Domain concepts

- **Employee:** current name, state, department, employee type, location, start date, and manager ID.
- **Group:** a named collection of employees that can supply policies to its members.
- **Employee group membership:** the many-to-many link between employees and groups.
- **Group policy:** the many-to-many link that makes a policy apply to every member of a group.
- **Condition tree:** nested `and`/`or` expressions over employee fields using `=`, `<`, and `<=` comparisons.
- **Compiled policy clause:** one flat set of conditions that must all match.
- **Employee policy:** a persisted match between an employee and a policy.
- **Field definition:** a named assignment field with `one` or `many` cardinality.
- **Policy:** a priority-ranked condition tree with assignment values.
- **Policy field value:** one relationally stored consequence of a policy.
- **Employee override:** one employee-specific field value that replaces policy results for that field.
- **Employee assignment:** a final resolved value supplied by exactly one policy or employee override.

## Install and run

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are expected.

```bash
uv sync
uv run fastapi dev main.py
```

The API runs at <http://127.0.0.1:8000>; interactive documentation is at <http://127.0.0.1:8000/docs>. By default, data is stored in `policy_assignments.db`, and missing tables are created on startup. Override it with a SQLAlchemy URL, for example `DATABASE_URL=sqlite:///./other.db`.

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
| GET / POST | `/employees/{id}/overrides` | List or create manual overrides |
| PATCH / DELETE | `/employees/{id}/overrides/{override_id}` | Update or remove an override |
| POST / GET | `/groups` | Create or list groups |
| GET / PATCH | `/groups/{id}` | Read or update a group |
| GET | `/groups/{id}/employees` | List group members |
| POST / DELETE | `/groups/{id}/employees/{employee_id}` | Add or remove a group member |
| GET | `/groups/{id}/policies` | List policies attached to a group |
| POST / DELETE | `/groups/{id}/policies/{policy_id}` | Attach or remove a group policy |
| POST / GET | `/field-definitions` | Create or list field definitions |
| GET | `/field-definitions/{id}` | Read a field definition |
| POST / GET | `/policies` | Create policies with values or list them |
| GET / PATCH | `/policies/{id}` | Read or update a policy and its values |

Employee creation and update automatically recalculate that employee. Creating or changing policy configuration intentionally does not reconcile all employees; use the explicit employee reconciliation endpoint.

Adding or removing a group membership recalculates the affected employee immediately. Attaching or removing a group policy recalculates every current member of that group in the same transaction. If resolution finds an equal-priority conflict, the membership or policy-link change is rolled back.

A group policy applies because of the explicit group link, even when its condition tree does not match the member directly. If a policy applies directly and through one or more groups, it is still considered only once. Policy origin can be derived from the membership and group-policy links; final assignments continue to record the winning `source_policy_id`.

Creating, updating, or removing an override recalculates only the employee's assignments; it does not rerun policy matching. Normal assignments have a `source_policy_id`, overridden assignments have a `source_override_id`, and a database check constraint requires exactly one of those sources.

## Alice example

Create `pay_schedule` (`one`) and `application_access` (`many`). Create a priority-20 policy conditioned on California that produces `biweekly` and `payroll_app`, and a priority-10 policy conditioned on Engineering that produces `weekly` and `GitHub`. Creating Alice in California Engineering automatically resolves:

```text
pay_schedule = biweekly
application_access = payroll_app
application_access = GitHub
```

Patching Alice's state to Wisconsin removes the California policy match and automatically leaves `weekly` and `GitHub`. The integration tests exercise this exact lifecycle.

## Version 1 boundaries

Version 1 intentionally excludes a frontend, PostgreSQL, policy versions and effective dates, historical evaluation, time-bounded overrides, override reasons and authorship, automatic company-wide reconciliation, workers and queues, caching, audit logs, authentication/authorization, simulation, and complex explainability.
