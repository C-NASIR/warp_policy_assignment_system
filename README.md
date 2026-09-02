# Warp Policy Assignment System

Version 1 is a FastAPI backend that records past assignments, serves current assignments, and calculates future assignments from date-effective policies.

## Architecture

The application uses FastAPI and Pydantic at the API boundary, explicit application services for domain behavior, SQLAlchemy 2 for persistence, and PostgreSQL through Psycopg 3. PostgreSQL is the only supported database for the API, worker, migrations, and tests. Alembic is configured for future migrations once persistent environments require them.

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

Read-only assignment queries distinguish three questions. A past date reads the
persisted `EmployeeAssignment` history at the start of that UTC date, today reads
the current persisted rows, and a future date runs stateless policy resolution
without changing policy links, assignments, schedules, or audit logs. Exact
historical instants remain available through the existing `as_of` timestamp.
Reconciliation uses the same stateless resolver for today and then persists its
calculated policy links and assignment differences.

`Policy` is the stable identity referenced by employees and groups. `PolicyVersion` is the executable definition containing priority, effective dates, conditions, compiled clauses, and field values. Policy condition trees are compiled into flat OR-of-AND clauses per version. Employee reconciliation selects the one version effective on the evaluation date, evaluates its clauses, persists stable policy links, and resolves each assignment field independently.

Policy-version API responses include the complete canonical condition tree using
the same nested `logical_operator`, `conditions`, and `child_groups` structure
accepted when creating a version. This lets clients inspect and round-trip a
stored rule without depending on its internal compiled representation.

Condition inputs are system-controlled `ConditionFieldDefinition` records, separate from assignment-output `AssignmentFieldDefinition` records. Static fields resolve trusted employee attributes; derived fields invoke allowlisted application resolvers. Definitions declare descriptions, data types, allowed operators, rule-builder input metadata, resolver keys, and dependency metadata, while canonical and compiled conditions retain foreign keys to those definitions. The condition-field API exposes that catalog so visual and agent clients can construct valid conditions without duplicating field-specific rules. Administrators select catalog fields but cannot define arbitrary formulas or executable resolvers.

`tenure` is a derived calendar-duration field resolved from `Employee.start_date` and the reconciliation evaluation date. Inputs such as `2 years` are normalized to `P2Y`; comparison uses completed calendar anniversaries rather than fixed 365-day intervals. A February 29 start date reaches its anniversary on February 28 in a non-leap year.

The employee reporting graph is a self-referencing `manager_id` relationship with database-enforced referential integrity. Policies can use the static `manager_id` reference or the derived `is_manager`, `direct_report_count`, `reports_under`, and `management_level` fields. `reports_under = N` matches any direct or indirect report beneath employee `N`; management level is the number of reporting hops from a root employee, so a root has level zero. Manager changes reject missing managers, self-management, and cycles. Dependency impact resolvers synchronously reconcile the moved employee and descendants plus the old and new managers in the same transaction.

Effective ranges are inclusive. Versions for one policy may not overlap, and an archived policy has no effective version. Scheduling a later version automatically closes the previous open-ended version on the preceding day. An effective-date gap is valid and means that policy contributes no behavior during the gap. Creating a future version immediately reconciles current state but does not apply that version early; automatic reconciliation when its effective date arrives remains a separate scheduling concern.

Future changes are represented centrally in `ScheduledReconciliation` while their authoritative dates remain on the owning domain records. Policy-version creation immediately synchronizes pending `becomes_effective` and `expires` events. Because `effective_until` is inclusive, expiration is scheduled for midnight UTC on the following day. The scheduling service can query and reconcile due events transactionally, but version 1 does not include a periodic worker that invokes it.

Groups are explicit collections of employees. A group contributes its attached policies as candidates for every member; it does not produce assignments of its own. Direct matches and group-inherited policies are deduplicated and sent through the same policy engine, so priority and conflict behavior is identical regardless of where a policy came from.

For cardinality `one`, the highest-priority effective policy version wins. Equal-priority versions producing different values return HTTP 409 instead of selecting arbitrarily. For cardinality `many`, unique values are retained. If several versions produce the same many-valued result, its recorded source is the highest-priority version, breaking remaining ties by lowest version ID.

Manual overrides are field values applied after normal policy resolution. If a field has overrides, all policy-derived values for that field are replaced by its override values. A `one` field accepts one override per employee; a `many` field accepts multiple unique override values. Overrides can also create an assignment when no policy supplies that field. They do not suppress policy conflicts, which remain configuration errors.

Employee assignments are temporal results, not independently versioned definitions. Each row has a UTC `effective_from` and optional `effective_until`, using a half-open `[effective_from, effective_until)` interval. Reconciliation compares the newly resolved result with open assignments: unchanged values and sources retain their rows, removed results are closed, and new or changed results create new rows. This preserves both what an employee had at an instant and the exact policy version or override that supplied it.

Every assignment also stores an immutable JSON explanation snapshot built during
resolution. Policy explanations record the winning policy and version, direct
condition evidence or group origins, the field's cardinality and selection
strategy, and competing candidates with their priorities and outcomes. Override
explanations identify the override and the policy values it replaced. A material
explanation change closes the old assignment and creates a new historical row
even when the final value and winning source remain unchanged. Past and current
reads return the stored explanation; future projections build the same shape in
memory without persisting it.

`AuditLog` is the system-wide mutation journal. Assignment history answers what was true at a point in time; audit logs answer what changed, when, and which actor caused it. Audit entries are written through one service in the same database transaction as the domain mutation, so both the mutation and its audit entries commit or roll back together. API mutations accept an optional `X-Actor` header and use `api` when it is omitted. Automated reconciliation always records assignment mutations as `system`.

Overrides are retained for provenance. Updating an override retires the old immutable row and creates a replacement; deleting one retires it. Only unretired overrides participate in current resolution, while historical assignments can continue referring to the override that produced them.

## Domain concepts

- **Employee:** current name, state, department, employee type, location, start date, and an optional self-referencing manager relationship.
- **Group:** a named collection of employees that can supply policies to its members.
- **Employee group membership:** the many-to-many link between employees and groups.
- **Group policy:** the many-to-many link that makes a policy apply to every member of a group.
- **Policy:** a stable named identity with `active` or `archived` status.
- **Policy version:** a date-effective, priority-ranked executable definition owned by one policy.
- **Condition field definition:** a system-controlled static or derived policy input with a trusted resolver, data type, and dependency metadata.
- **Condition tree:** a version-owned nested `and`/`or` expression over condition fields using `=`, `<`, `<=`, `>`, and `>=` comparisons.
- **Compiled policy clause:** one version-owned flat set of conditions that must all match.
- **Employee policy:** a persisted match between an employee and a policy.
- **Assignment field definition:** a named assignment output with `one` or `many` cardinality.
- **Policy field value:** one relationally stored consequence of a policy version.
- **Employee override:** one employee-specific field value that replaces policy results for that field; retired rows remain available as historical sources.
- **Employee assignment:** a time-bounded resolved value supplied by exactly one policy version or employee override, with an immutable explanation of the decision.
- **Audit log:** an append-only actor, entity, action, before/after snapshot, and timestamp for an important domain mutation.
- **Approved change execution:** an idempotency record tying one signed preview approval to its committed response and actor.
- **Scheduled reconciliation:** a centralized pending, processed, or cancelled future trigger referencing the domain entity whose date caused it.

## Install and run

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are expected.

```bash
uv sync
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/policy_assignments
export CHANGE_APPROVAL_SECRET="$(openssl rand -hex 32)"
uv run fastapi dev main.py
```

The API runs at <http://127.0.0.1:8000>; interactive documentation is at <http://127.0.0.1:8000/docs>. A PostgreSQL server and database must exist before startup. The URL above is also the local default when `DATABASE_URL` is omitted; set it explicitly outside local development. Plain `postgresql://` URLs are accepted and normalized to the installed Psycopg 3 driver. Any non-PostgreSQL URL is rejected at startup. Missing tables are created on startup. The Alembic scaffold is retained for future persistent environments, but there are currently no migration revisions.

Audit-log reads are protected separately because the application does not yet have user authentication. Set `AUDIT_ADMIN_KEY` and send the same value in `X-Audit-Key`. If the environment variable is absent, audit reads return HTTP 503; a missing or incorrect header returns HTTP 403. In production, inject this value through the deployment secret manager and replace this narrow boundary when application-wide authentication is added.

Approved execution requires `CHANGE_APPROVAL_SECRET` containing at least 32
bytes of secret material. Store it in the deployment secret manager and use the
same value for every API process. `CHANGE_APPROVAL_TTL_SECONDS` controls token
lifetime and defaults to 900 seconds; values are constrained to 60–3600 seconds.
Without a valid secret, previews still work but return no approval token and
include a warning, while execution requests are rejected.

Run tests with:

```bash
createdb -U postgres policy_assignments_test
TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/policy_assignments_test \
uv run pytest
```

Tests create and drop all application tables, so `TEST_DATABASE_URL` must point to a dedicated disposable PostgreSQL database. It defaults to the local `policy_assignments_test` database shown above.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Health check |
| POST / GET | `/employees` | Create or list employees |
| GET / PATCH / DELETE | `/employees/{id}` | Read, update, or delete an employee |
| GET | `/employees/{id}/assignments` | Read current assignments, or assignments at an optional `as_of` UTC timestamp |
| GET | `/employees/{id}/assignments/history` | Read complete assignment history |
| POST | `/employees/{id}/refresh` | Recompute matching policies and assignments |
| POST | `/assignment-queries` | Query recorded past, persisted present, or calculated future assignments for an employee batch |
| POST | `/change-previews` | Simulate a supported mutation and return assignment differences without persisting it |
| POST | `/change-executions` | Execute an unchanged, signed preview exactly once |
| GET / POST | `/employees/{id}/overrides` | List or create manual overrides |
| PATCH / DELETE | `/employees/{id}/overrides/{override_id}` | Update or remove an override |
| POST / GET | `/groups` | Create or list groups |
| GET / PATCH | `/groups/{id}` | Read or update a group |
| GET | `/groups/{id}/employees` | List group members |
| POST / DELETE | `/groups/{id}/employees/{employee_id}` | Add or remove a group member |
| GET | `/groups/{id}/policies` | List policies attached to a group |
| POST / DELETE | `/groups/{id}/policies/{policy_id}` | Attach or remove a group policy |
| POST / GET | `/assignment-fields` | Create or list assignment field definitions |
| GET | `/assignment-fields/{id}` | Read an assignment field definition |
| GET | `/condition-fields` | List system-supported condition fields and dependencies |
| GET | `/condition-fields/{key}` | Read one system-supported condition field |
| POST / GET | `/policies` | Create policies with version 1 or list them |
| GET / PATCH | `/policies/{id}` | Read or update stable policy metadata |
| GET / POST | `/policies/{id}/versions` | List or create policy versions |
| GET | `/policies/{id}/versions/{version_id}` | Read one policy version |
| GET | `/audit-logs` | Read authorized, filterable audit events |

Employee creation and ordinary scalar updates automatically recalculate that employee. A reporting change additionally recalculates the old and new managers and the moved employee's complete subtree, deduplicating all affected IDs at one reconciliation timestamp. Deleting an employee clears direct reports' manager references, cancels that employee's pending reconciliation events, and recalculates the affected reporting subtree. Creating a policy, adding a version, or changing its active/archived status synchronously recalculates every employee in the same transaction. A policy rule can make previously unaffected employees start matching, so the current-scale implementation conservatively scans all employees; this candidate set can be optimized later. Name-only policy changes do not reconcile because they cannot affect results.

Adding or removing a group membership recalculates the affected employee immediately. Attaching or removing a group policy recalculates every current member of that group in the same transaction. If resolution finds an equal-priority conflict, the employee, group, or policy mutation and all partial reconciliation and audit changes are rolled back together.

An active group policy with a currently effective version applies because of the explicit group link, even when that version's condition tree does not match the member directly. Archived, expired, and not-yet-effective group policies are excluded from current `EmployeePolicy` links. If a policy applies directly and through one or more groups, it is still considered only once. Policy origin can be derived from the membership and group-policy links; final assignments record the winning `source_policy_version_id`.

Creating, updating, or removing an override recalculates only the employee's assignments; it does not rerun policy matching. Normal assignments have a `source_policy_version_id`, overridden assignments have a `source_override_id`, and a database check constraint requires exactly one of those sources. Override updates return a new override ID because the previous row is retired for provenance.

Reconciliation is chronological and persists assignment history. Calls older than the latest stored assignment start are rejected instead of rewriting established history. `GET /employees/{id}/assignments` returns the values effective now by default; `as_of` uses half-open interval boundaries, and the history endpoint returns both open and closed rows.

`POST /assignment-queries` accepts `employee_ids` and an `evaluation_date`. It
deduplicates the batch and returns one of three explicit modes:

- `recorded_history` for a past date, using persisted assignment rows at the
  start of that UTC date.
- `current_persisted` for today, using the current assignment projection.
- `calculated_future` for a future date, rerunning matching, effective policy
  version selection, conditions, conflict resolution, and active overrides
  without persistence.

Future calculation uses the employee facts, reporting relationships, group
links, policy active/archive status, and unretired overrides currently stored.
Policy-version effective ranges and date-derived facts such as tenure use the
requested evaluation date. Scheduling future employee facts, group changes,
policy status changes, or time-bounded overrides remains outside version 1.
Assignment values in every mode include an `explanation`: recorded history and
current state load the saved snapshot, while calculated future results return a
new, unpersisted snapshot for the requested evaluation date.

## Change preview contract

`POST /change-previews` accepts a discriminated change request and runs the same
domain mutation and reconciliation services used by real writes inside a
database savepoint that is always rolled back. It supports employee creation and
updates, policy-version creation, group membership changes, and override
creation, updates, and deletion. The response contains per-employee before and
after assignments, added and removed assignments, field-level changes, warnings,
and conflicts. Proposed employees have a null employee ID; assignments supplied
by a proposed policy version or override have a null source ID and
`source_is_proposed: true`. Domain rows, policy links, assignment history, audit
logs, and scheduled reconciliation records are not retained after a preview.

## Approved-change execution contract

A successful preview includes a signed, expiring `approval` containing an
approval ID, token, exact-change digest, preview-impact digest, and expiry time.
It also signs a digest of the target employee, policy versions, membership, or
override state relevant to that mutation. The token contains only identifiers,
timestamps, and digests—the submitted employee or policy data is not embedded
in it. Call `POST /change-executions` with that token and the exact same
discriminated `change` object.

Execution verifies the signature and expiry, rejects altered input, locks and
checks the target-state precondition, applies the change and reconciliation in
one transaction, and recomputes the comparable before/after impact. A changed
target or changed impact rolls the whole transaction back with
`change_approval_stale`; impact-drift errors include the current uncommitted
preview so the client can show what changed and request new approval. A
successful response returns real created resource IDs and actual assignment
changes.

The approval ID is persisted with the successful response. Retrying the same
token and change returns that response with `replayed: true` instead of applying
the mutation again, including after token expiry. PostgreSQL advisory transaction
locking serializes concurrent executions of the same approval. Tokens are
bearer capabilities until application-wide authentication is added and must not
be logged or exposed to unrelated users.

## Error contract

Conflict (`409`) and validation (`422`) responses include a stable `error`
object for the UI and MCP clients. It contains a category, application-level
code, human-readable message, and one or more issues with a machine-readable
code, request or domain path, and structured metadata. Request validation issues
preserve Pydantic's error code and exact input location. Policy-assignment
conflicts additionally identify the assignment field, winning priority, and all
conflicting policy/version/value candidates. Change previews return the same
conflict issue shape in their `conflicts` collection.

The original FastAPI `detail` member remains in `409` and `422` responses for
backward compatibility. New clients should consume `error`; `detail` is a
transition field and should not be parsed for business logic.

## Auditing contract

The current action vocabulary is:

- `Policy`: `created`, `changed`, `archived`
- `PolicyVersion`: `created`; `before` is the preceding version snapshot when one exists
- `Group`: `created`, `changed`, `employee_added`, `employee_removed`, `policy_attached`, `policy_detached`
- `Employee`: `created`, `changed`, `manager_changed`, `deleted`
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

Tenure scheduling is also maintained immediately. Employee creation, `start_date` changes, policy creation/versioning, and policy archive/reactivation recompute desired future anniversary events. Stale pending events are cancelled and exact desired events are created or restored idempotently. `>= N years` changes at anniversary `N`; `> N` and `<= N` change at anniversary `N + 1`; equality schedules both its entry and exit anniversaries. Events outside the policy version's effective range are omitted because version-boundary reconciliation already covers those changes.

`reconcile_due_events()` is the callable processing boundary for the worker. It locks and loads one due batch, deduplicates simultaneous events belonging to the same policy, invokes the existing policy or employee reconciliation paths, and marks events processed only after successful reconciliation. Domain mutations, assignments, audit entries, and schedule status share one transaction; a conflict rolls everything back and leaves the event pending for retry.

The service creates employee tenure-threshold events and also defines dispatch types for future override activation/expiration. Time-bounded override schedule creation remains deferred. No internal timer invokes the processor automatically; the one-shot worker is intended to be called by an external scheduler.

## Reconciliation worker

The project includes a PostgreSQL-only, one-shot worker command:

```bash
DATABASE_URL=postgresql+psycopg://user:password@host/database \
uv run python -m app.workers.reconciliation
```

The worker does not create tables or discover future dates from domain tables. It expects the application schema to exist, obtains a PostgreSQL advisory lock so overlapping invocations cannot run, and repeatedly calls `reconcile_due_events()` in independent transactions until the due queue is drained or its runtime budget is reached. `FOR UPDATE SKIP LOCKED` protects claimed event rows. A failed batch rolls back and makes the command exit unsuccessfully while its events remain pending.

Configuration:

- `RECONCILIATION_BATCH_SIZE`: due events per transaction; default `50`
- `RECONCILIATION_MAX_RUNTIME_SECONDS`: maximum drain time; default `900`
- `RECONCILIATION_ADVISORY_LOCK_KEY`: positive PostgreSQL advisory-lock key
- `LOG_LEVEL`: standard Python log level; default `INFO`

The command exits successfully without processing when another invocation owns the advisory lock. It is designed to be invoked hourly by an external scheduler; it does not contain an internal timer or sleep loop.

## Alice example

Create `pay_schedule` (`one`) and `application_access` (`many`). Create a priority-20 policy whose initial version is conditioned on California and produces `biweekly` and `payroll_app`, and a priority-10 policy whose initial version is conditioned on Engineering and produces `weekly` and `GitHub`. Creating Alice in California Engineering automatically resolves:

```text
pay_schedule = biweekly
application_access = payroll_app
application_access = GitHub
```

Patching Alice's state to Wisconsin removes the California policy match and automatically leaves `weekly` and `GitHub`. The integration tests exercise this exact lifecycle.

## Version 1 boundaries

Version 1 intentionally excludes a frontend, retroactive assignment-history rewriting, scheduled future employee facts and relationship changes, time-bounded overrides, override reasons and authorship, administrator-defined condition formulas, an internal worker timer or deployment scheduler, queues, caching, and application-wide authentication/authorization beyond the audit-read key.
