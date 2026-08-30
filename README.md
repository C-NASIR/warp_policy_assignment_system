# Warp Policy Assignment System

Version 1 is a small FastAPI backend that answers: given an employee's current facts, which field values should be assigned to them now?

## Architecture

The application uses FastAPI and Pydantic at the API boundary, explicit application services for domain behavior, SQLAlchemy 2 for persistence, and SQLite as the local database. Alembic is configured for future migrations once persistent environments require them. Database access is kept behind SQLAlchemy sessions, so a later PostgreSQL move primarily requires changing `DATABASE_URL`.

```text
Employee
→ Direct Compiled Policy Matching + Group Policies
→ Stable Employee Policies
→ Effective Policy Versions
→ Candidate Field Values
→ Conflict Resolution
→ Employee Overrides
→ Temporal Employee Assignments
```

`Policy` is the stable identity referenced by employees and groups. `PolicyVersion` is the executable definition containing priority, effective dates, conditions, compiled clauses, and field values. Policy condition trees are compiled into flat OR-of-AND clauses per version. Employee reconciliation selects the one version effective on the evaluation date, evaluates its clauses, persists stable policy links, and resolves each assignment field independently.

Effective ranges are inclusive. Versions for one policy may not overlap, and an archived policy has no effective version. Scheduling a later version automatically closes the previous open-ended version on the preceding day. An effective-date gap is valid and means that policy contributes no behavior during the gap. Creating a future version immediately reconciles current state but does not apply that version early; automatic reconciliation when its effective date arrives remains a separate scheduling concern.

Future changes are represented centrally in `ScheduledReconciliation` while their authoritative dates remain on the owning domain records. Policy-version creation immediately synchronizes pending `becomes_effective` and `expires` events. Because `effective_until` is inclusive, expiration is scheduled for midnight UTC on the following day. The scheduling service can query and reconcile due events transactionally, but version 1 does not include a periodic worker that invokes it.

Groups are explicit collections of employees. A group contributes its attached policies as candidates for every member; it does not produce assignments of its own. Direct matches and group-inherited policies are deduplicated and sent through the same policy engine, so priority and conflict behavior is identical regardless of where a policy came from.

For cardinality `one`, the highest-priority effective policy version wins. Equal-priority versions producing different values return HTTP 409 instead of selecting arbitrarily. For cardinality `many`, unique values are retained. If several versions produce the same many-valued result, its recorded source is the highest-priority version, breaking remaining ties by lowest version ID.

Manual overrides are field values applied after normal policy resolution. If a field has overrides, all policy-derived values for that field are replaced by its override values. A `one` field accepts one override per employee; a `many` field accepts multiple unique override values. Overrides can also create an assignment when no policy supplies that field. They do not suppress policy conflicts, which remain configuration errors.

Employee assignments are temporal results, not independently versioned definitions. Each row has a UTC `effective_from` and optional `effective_until`, using a half-open `[effective_from, effective_until)` interval. Reconciliation compares the newly resolved result with open assignments: unchanged values and sources retain their rows, removed results are closed, and new or changed results create new rows. This preserves both what an employee had at an instant and the exact policy version or override that supplied it.

`AuditLog` is the system-wide mutation journal. Assignment history answers what was true at a point in time; audit logs answer what changed, when, and which actor caused it. Audit entries are written through one service in the same database transaction as the domain mutation, so both the mutation and its audit entries commit or roll back together. API mutations accept an optional `X-Actor` header and use `api` when it is omitted. Automated reconciliation always records assignment mutations as `system`.

Overrides are retained for provenance. Updating an override retires the old immutable row and creates a replacement; deleting one retires it. Only unretired overrides participate in current resolution, while historical assignments can continue referring to the override that produced them.

## Domain concepts

- **Employee:** current name, state, department, employee type, location, start date, and manager ID.
- **Group:** a named collection of employees that can supply policies to its members.
- **Employee group membership:** the many-to-many link between employees and groups.
- **Group policy:** the many-to-many link that makes a policy apply to every member of a group.
- **Policy:** a stable named identity with `active` or `archived` status.
- **Policy version:** a date-effective, priority-ranked executable definition owned by one policy.
- **Condition tree:** a version-owned nested `and`/`or` expression over employee fields using `=`, `<`, and `<=` comparisons.
- **Compiled policy clause:** one version-owned flat set of conditions that must all match.
- **Employee policy:** a persisted match between an employee and a policy.
- **Field definition:** a named assignment field with `one` or `many` cardinality.
- **Policy field value:** one relationally stored consequence of a policy version.
- **Employee override:** one employee-specific field value that replaces policy results for that field; retired rows remain available as historical sources.
- **Employee assignment:** a time-bounded resolved value supplied by exactly one policy version or employee override.
- **Audit log:** an append-only actor, entity, action, before/after snapshot, and timestamp for an important domain mutation.
- **Scheduled reconciliation:** a centralized pending, processed, or cancelled future trigger referencing the domain entity whose date caused it.

## Install and run

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are expected.

```bash
uv sync
uv run fastapi dev main.py
```

The API runs at <http://127.0.0.1:8000>; interactive documentation is at <http://127.0.0.1:8000/docs>. By default, data is stored in `policy_assignments.db`, and missing tables are created on startup. Override it with a SQLAlchemy URL, for example `DATABASE_URL=sqlite:///./other.db`. The development database is disposable: after a model change, remove the old `.db` file and restart. The Alembic scaffold is retained for future persistent environments, but there are currently no migration revisions.

Audit-log reads are protected separately because the application does not yet have user authentication. Set `AUDIT_ADMIN_KEY` and send the same value in `X-Audit-Key`. If the environment variable is absent, audit reads return HTTP 503; a missing or incorrect header returns HTTP 403. In production, inject this value through the deployment secret manager and replace this narrow boundary when application-wide authentication is added.

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
| GET | `/employees/{id}/assignments` | Read current assignments, or assignments at an optional `as_of` UTC timestamp |
| GET | `/employees/{id}/assignments/history` | Read complete assignment history |
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
| POST / GET | `/policies` | Create policies with version 1 or list them |
| GET / PATCH | `/policies/{id}` | Read or update stable policy metadata |
| GET / POST | `/policies/{id}/versions` | List or create policy versions |
| GET | `/policies/{id}/versions/{version_id}` | Read one policy version |
| GET | `/audit-logs` | Read authorized, filterable audit events |

Employee creation and update automatically recalculate that employee. Creating a policy, adding a version, or changing its active/archived status synchronously recalculates every employee in the same transaction. A policy rule can make previously unaffected employees start matching, so the current-scale implementation conservatively scans all employees; this candidate set can be optimized later. Name-only policy changes do not reconcile because they cannot affect results.

Adding or removing a group membership recalculates the affected employee immediately. Attaching or removing a group policy recalculates every current member of that group in the same transaction. If resolution finds an equal-priority conflict, the employee, group, or policy mutation and all partial reconciliation and audit changes are rolled back together.

An active group policy with a currently effective version applies because of the explicit group link, even when that version's condition tree does not match the member directly. Archived, expired, and not-yet-effective group policies are excluded from current `EmployeePolicy` links. If a policy applies directly and through one or more groups, it is still considered only once. Policy origin can be derived from the membership and group-policy links; final assignments record the winning `source_policy_version_id`.

Creating, updating, or removing an override recalculates only the employee's assignments; it does not rerun policy matching. Normal assignments have a `source_policy_version_id`, overridden assignments have a `source_override_id`, and a database check constraint requires exactly one of those sources. Override updates return a new override ID because the previous row is retired for provenance.

Reconciliation is chronological and persists assignment history. Calls older than the latest stored assignment start are rejected instead of rewriting established history. `GET /employees/{id}/assignments` returns the values effective now by default; `as_of` uses half-open interval boundaries, and the history endpoint returns both open and closed rows.

## Auditing contract

The current action vocabulary is:

- `Policy`: `created`, `changed`, `archived`
- `PolicyVersion`: `created`; `before` is the preceding version snapshot when one exists
- `Group`: `created`, `changed`, `employee_added`, `employee_removed`, `policy_attached`, `policy_detached`
- `EmployeeOverride`: `created`, `changed`, `removed`
- `EmployeeAssignment`: `created`, `ended`

An assignment replacement is intentionally two events: `ended` for the old assignment followed by `created` for the replacement. Unchanged reconciliation results and idempotent group operations produce no events.

Snapshots contain JSON-safe mapped scalar values for the affected entity. Policy-version snapshots additionally contain field values and compiled clauses; assignment snapshots include the field name. Scalar dates and timestamps use ISO 8601 strings. The shared snapshot helper automatically replaces columns named `password`, `token`, `access_token`, `api_key`, or `secret` with `[REDACTED]`, and callers must explicitly redact any other sensitive fields introduced later. Audit payloads must never contain credentials or unnecessary employee data.

`GET /audit-logs` supports `entity_type`, `entity_id`, `actor`, `action`, `from_timestamp`, and `to_timestamp` filters, plus bounded `limit` and `offset` pagination. Results are chronological. There is no mutation or deletion endpoint: audit records are append-only and retained indefinitely in version 1. Any future retention process must be explicitly approved, documented, and run outside ordinary domain mutation paths.

## Scheduled reconciliation contract

`ScheduledReconciliation` contains `entity_type`, `entity_id`, `trigger_type`, `scheduled_at`, `status`, and `processed_at`. An indexed `(status, scheduled_at)` lookup lets a future worker find pending work without scanning policy versions, employees, or overrides. Exact event identity is unique, so scheduling the same event repeatedly is idempotent.

Policy scheduling is maintained immediately whenever a version is created or policy status changes:

- A future `effective_from` creates a `PolicyVersion/becomes_effective` event.
- An inclusive `effective_until` creates a `PolicyVersion/expires` event at the start of the next UTC day.
- Closing a prior open-ended version creates its expiration event at the new version's boundary.
- Archiving a policy cancels its pending events; reactivation restores future events without duplicating rows.

`reconcile_due_events()` is the callable processing boundary for a future worker. It locks and loads one due batch, deduplicates simultaneous events belonging to the same policy, invokes the existing policy or employee reconciliation paths, and marks events processed only after successful reconciliation. Domain mutations, assignments, audit entries, and schedule status share one transaction; a conflict rolls everything back and leaves the event pending for retry.

The service already defines dispatch types for employee tenure thresholds and override activation/expiration. Creating those schedules remains deferred until tenure conditions and time-bounded override fields exist. No timer, cron process, queue, or worker is currently running.

## Alice example

Create `pay_schedule` (`one`) and `application_access` (`many`). Create a priority-20 policy whose initial version is conditioned on California and produces `biweekly` and `payroll_app`, and a priority-10 policy whose initial version is conditioned on Engineering and produces `weekly` and `GitHub`. Creating Alice in California Engineering automatically resolves:

```text
pay_schedule = biweekly
application_access = payroll_app
application_access = GitHub
```

Patching Alice's state to Wisconsin removes the California policy match and automatically leaves `weekly` and `GitHub`. The integration tests exercise this exact lifecycle.

## Version 1 boundaries

Version 1 intentionally excludes a frontend, PostgreSQL, retroactive assignment-history rewriting, policy simulation that does not persist results, time-bounded overrides, override reasons and authorship, tenure-threshold calculation, a periodic scheduled-reconciliation worker, queues, caching, application-wide authentication/authorization beyond the audit-read key, and complex explainability beyond persisted source provenance and audit snapshots.
