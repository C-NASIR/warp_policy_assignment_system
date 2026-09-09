# PolicyOS workflow audit

Audit date: 2026-09-06

This audit combines frontend inspection with backend tests and service
documentation. “Verified” means the behavior has direct implementation and test
evidence. “UI verified” means the path and controls exist but the audit did not
execute a connected browser session. Claims about domain behavior should follow
the backend evidence, which is the source of truth.

## Assignment lifecycle

```text
Employee facts and reporting relationships
  -> direct policy matching + explicit group policies
  -> effective policy version for the evaluation date
  -> candidate values per assignment field
  -> cardinality and priority resolution
  -> field-level manual overrides
  -> temporal employee assignments
  -> assignment explanation, assignment history, and audit events
```

## Visible workflows

| Workflow | UI entry | Current behavior | Evidence | Status |
| --- | --- | --- | --- | --- |
| Overview health | `/dashboard` | Shows assignment coverage, active policies, current assignments, overrides, and recent audit activity | `frontend/app/dashboard/page.tsx`, `backend/tests/test_impact_summaries.py` | UI verified |
| Browse employees | `/employees` | Lists visible employees and supports client-side search/filtering | `frontend/app/employees/page.tsx`, `frontend/components/employee-directory.tsx`, `backend/tests/test_collection_filtering.py` | Verified |
| Onboard or edit employee | `/employees/new`, `/employees/{id}` | Collects trusted facts, requests a change preview, then saves or executes an approved preview; reconciliation updates downstream assignments | `frontend/components/employee-form.tsx`, `backend/tests/test_change_previews.py`, `backend/tests/test_policy_change_reconciliation.py` | Verified |
| Inspect assignments | `/employees/{id}` | Displays current resolved values; expanding a card shows policy, direct condition evidence or group origin, priority, and override replacement details | `frontend/components/assignment-card.tsx`, `backend/tests/test_assignment_explanations.py` | Verified |
| Review history | `/employees/{id}` | Shows open and retired assignment rows with source and effective interval | `frontend/components/override-manager.tsx`, `backend/tests/test_assignment_history.py` | Verified |
| Manage overrides | `/employees/{id}` | Previews create, update, or removal; an active override replaces all policy values for that field and reconciliation is audited | `frontend/components/override-manager.tsx`, `backend/tests/test_overrides.py`, `backend/tests/test_audit_logs.py` | Verified |
| Browse policy impact | `/policies`, `/policies/{id}` | Separates matched employees from employees and values actually selected after resolution | `frontend/app/policies/[id]/page.tsx`, `backend/tests/test_impact_summaries.py` | Verified |
| Create a policy | `/policies/new` | Builds conditions, one or more assignment values, priority, and dates; a newly created policy may be active or draft depending on authority | `frontend/components/policy-builder.tsx`, `backend/tests/test_policy_versions.py` | UI verified |
| Create a policy version | `/policies/new?policyId={id}` | Uses the connected preview contract; active-policy versions require activation authority and can create a persisted human approval request | `frontend/components/policy-builder.tsx`, `backend/tests/test_policy_access.py`, `backend/tests/test_change_executions.py` | Verified |
| Activate or archive | `/policies/{id}` | Uses record capabilities and reconciles affected employee assignments immediately | `frontend/components/policy-lifecycle.tsx`, `backend/tests/test_policy_change_reconciliation.py` | Verified |
| Manage groups | `/groups`, `/groups/{id}` | Groups are explicit; membership changes are previewed, while policy attachment and detachment reconcile members immediately | `frontend/components/group-manager.tsx`, `backend/tests/test_groups.py` | Verified |
| Review approvals | `/approvals` | Another user can approve or reject a pending request; the ordinary approving user executes it; Root may execute an approved request; the author cannot approve it | `frontend/components/approval-queue.tsx`, `backend/app/services/approval_requests.py`, `backend/tests/test_change_executions.py` | Verified |
| Configure assignment fields | `/settings` | Creates named `one` or `many` output fields; cardinality is fixed after creation | `frontend/components/assignment-field-manager.tsx`, `backend/app/models.py` | UI verified |
| Inspect audit | `/audit` | Filters recent append-only events and exposes actor, entity, action, timestamp, and before/after snapshots | `frontend/components/audit-log-explorer.tsx`, `backend/tests/test_audit_logs.py` | Verified |
| Manage users and roles | `/access` | Provisions users, links employees, assigns roles, and defines permission, employee, and assignment-field scopes | `frontend/components/access-manager.tsx`, `backend/tests/test_access_control.py`, `backend/tests/test_employee_visibility.py`, `backend/tests/test_assignment_field_visibility.py` | Verified |
| Review access risk | `/access/review` | Reports privileged users without MFA, stale users, unused roles, and broad scopes | `frontend/app/access/review/page.tsx`, `backend/tests/test_security_hardening.py` | Verified |
| Manage account security | `/account/security` | Changes password, enrolls or disables MFA, performs step-up authentication, revokes sessions, and acknowledges events | `frontend/components/security-form.tsx`, `backend/tests/test_security_hardening.py` | Verified |
| Quick Find | Command/Ctrl+K | Searches a fixed permission-filtered list of application pages and actions | `frontend/components/app-shell.tsx` | UI verified |

## Domain claims approved for content

| Claim | Verification source |
| --- | --- |
| Policy is a stable identity; policy versions contain executable conditions, values, priority, and effective dates | `backend/app/models.py`, `backend/tests/test_policy_versions.py` |
| Conditions can use static employee facts and allowlisted derived tenure and organization fields | `backend/app/services/condition_fields.py`, `backend/tests/test_tenure_rules.py`, `backend/tests/test_org_chart_rules.py` |
| Nested conditions are compiled to OR-of-AND clauses, but authors work with the canonical tree | `backend/app/services/policy_compiler.py`, `backend/tests/test_policy_compiler.py`, `backend/tests/test_policy_versions.py` |
| Policy-version effective dates are inclusive; versions cannot overlap; a gap means no behavior | `backend/tests/test_policy_versions.py`, `backend/app/models.py` |
| A later version closes the prior open-ended version on the preceding date | `backend/tests/test_policy_versions.py` |
| For `one`, highest priority wins; different values at equal priority are a conflict | `backend/app/services/assignment_resolution.py`, `backend/tests/test_services.py` |
| For `many`, unique values are retained; duplicate values keep the highest-priority source, then lowest version ID | `backend/app/services/assignment_resolution.py`, `backend/README.md` |
| Groups are explicit and attached policies become candidates for every member regardless of direct condition match | `backend/tests/test_groups.py`, `backend/tests/test_policy_change_reconciliation.py` |
| Direct and group origins for the same policy are deduplicated | `backend/tests/test_groups.py` |
| An override replaces policy-derived values for its field and is retained for provenance when updated or removed | `backend/tests/test_overrides.py`, `backend/app/services/overrides.py` |
| Overrides do not suppress policy conflicts | `backend/tests/test_overrides.py` |
| Past assignment queries read recorded history, today reads persisted state, and future queries calculate without persistence | `backend/tests/test_assignment_queries.py` |
| Assignment history answers what was true; audit answers what changed, when, and by whom | `backend/tests/test_assignment_history.py`, `backend/tests/test_audit_logs.py` |
| The first user is Root with wildcard permission and unrestricted data visibility; Root still uses authentication, validation, and applicable security controls | `backend/app/services/human_auth.py`, `backend/app/services/access_control.py`, `backend/app/dependencies.py`, `backend/tests/test_access_control.py`, `backend/tests/test_security_hardening.py` |
| An employee record does not create a user; a user may link to an employee, and a non-Root user must have at least one explicit role at creation | `backend/app/services/access_control.py`, `backend/tests/test_access_control.py` |
| Human access is the union of allow-only role permissions plus separately unioned employee and assignment-field scopes | `backend/app/services/access_control.py`, `backend/app/services/employee_visibility.py`, `backend/app/services/assignment_field_visibility.py`, `backend/tests/test_access_control.py`, `backend/tests/test_employee_visibility.py`, `backend/tests/test_assignment_field_visibility.py` |
| Reporting-tree scope includes the linked employee plus direct and indirect descendants; a manager relationship alone grants no account or permission | `backend/app/services/employee_visibility.py`, `backend/app/services/org_chart.py`, `backend/tests/test_employee_visibility.py` |
| Policies produce employee assignments only; user roles are assigned and revoked explicitly through access administration | `backend/app/models.py`, `backend/app/services/access_control.py`, `backend/tests/test_access_control.py` |

## Route and permission map

| Route | Read or entry permission | Mutation permission(s) or capability |
| --- | --- | --- |
| `/dashboard` | Wildcard (`*`) in connected navigation; its data calls also require their own read access | Links shown by page are not individually gated in the current page |
| `/employees` | `employees:read` | `employees:create` |
| `/employees/new` | `employees:create` | `changes:preview` and the applicable create/execute authority in connected mode |
| `/employees/{id}` | `employees:read`; employee scope also applies | `employees:update`, `assignments:read`, `assignments:manage` |
| `/policies` | `policies:read`; assignment-field scope also applies | `policies:create` |
| `/policies/{id}` | `policies:read` plus record access | Record capabilities combine scope, state, and `policies:version:create`, `policies:activate`, or `policies:archive` |
| `/groups` | `groups:read` | `groups:create` |
| `/groups/{id}` | `groups:read` | `groups:update` |
| `/approvals` | `changes:approve` | `changes:approve`, `changes:execute` and request-specific capability |
| `/settings` | `settings:read` | `settings:manage` |
| `/audit` | `audit:read` | Read only |
| `/access` | `access:read` | `access:manage` |
| `/access/review` | `access:review` | Read only |
| `/account/security` | Any signed-in user | Identity checks and recent reauthentication can apply |

The backend is authoritative. Out-of-scope direct resources can return 404 to
avoid disclosing their existence. Documentation should say “you may not have
access” rather than promising that every inaccessible record returns 403.

## Demo-mode audit

Demo mode is available when `POLICY_API_URL` is unset. It is useful for reading
screens and trying controls, but it differs from connected behavior:

- Mutations update local component state or show a success message and are lost
  on refresh.
- Employee previews use a small hard-coded matcher in
  `frontend/components/employee-form.tsx`.
- The new-policy preview counts matches in the browser. Connected version
  previews use the backend change-preview contract.
- Approval buttons are disabled and the demo has no persisted approval queue.
- Demo assignments are curated samples and are not a complete recalculation of
  every listed employee, policy, and group relationship.
- The dashboard sentence about scheduled changes and conflicts is static copy;
  do not cite it as system state.

Content must label demo-only walkthroughs and must never claim that a demo
mutation persisted or exercised separation of duties.

## Current gaps and content constraints

| Gap | Content decision |
| --- | --- |
| No separate employee self-service portal | Describe self scope as a restricted view in the normal PolicyOS application |
| No built-in approval notification, arbitrary reviewer assignment, or request-search box | Use the request ID and the team's normal handoff process; do not promise messaging |
| No frontend workflow for batch future assignment queries | Teach the distinction between future calculation and current stored assignments; reserve an API procedure for later reference |
| No frontend UI for scheduled reconciliation operations or machine credentials | Do not promise UI steps; cover only verified concepts or later API reference |
| First-policy preview is not the same connected engine preview used by a new version | Describe it as a population estimate and verify the saved result |
| Group membership is previewed, but policy attach/detach is immediate | Keep the steps distinct; do not say every group change has a preview |
| Persisted approval is limited to supported human policy flows | Do not imply that every preview or denied mutation enters the approval queue |
| Demo data is not the curriculum fixture | Use an isolated Rachel/Morgan/Jordan training fixture and do not infer connected behavior from demo state |

## Reverification triggers

Reaudit affected content when any of these change:

- a route, page heading, navigation label, or Quick Find command;
- the permission catalog or record capability calculation;
- assignment cardinality, priority, conflict, group, or override semantics;
- preview or approval request types;
- the demo-data contract;
- effective-date or scheduled reconciliation behavior;
- employee, policy, group, assignment, audit, access, or security UI controls.
