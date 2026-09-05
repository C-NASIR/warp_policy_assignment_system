# Learner audiences and shared scenario

## Audience model

PolicyOS is currently an administrative assignment system, not an employee
self-service portal. The learning center therefore organizes material by the
job a signed-in operator needs to do, while keeping concepts readable by anyone.

| Audience | Primary need | Must be able to explain or do | Typical permissions |
| --- | --- | --- | --- |
| New operator | Understand the system before changing data | Explain why an employee received a value and where to investigate | `employees:read`, `assignments:read`, sometimes `policies:read` and `groups:read` |
| People operator | Onboard and maintain employee facts safely | Preview assignment effects, save an employee change, and recognize downstream reconciliation | `employees:read`, `employees:create`, `employees:update`, `assignments:read`, `changes:preview` |
| Policy author | Define workforce rules | Choose condition fields and outputs, set effective dates and priority, preview impact, and create versions | `policies:read`, `policies:create`, `policies:version:create`, `settings:read`, `changes:preview` |
| Policy activator | Control production policy behavior | Activate, archive, or authorize versions without conflating authorship and activation | `policies:activate`, `policies:archive` |
| Group manager | Maintain explicit populations | Add or remove members, attach policies, and predict immediate reconciliation | `groups:read`, `groups:create`, `groups:update`, plus related read permissions |
| Approver | Review sensitive changes independently | Inspect the exact change and impact, approve or reject another author's request, and execute an approved request | `changes:approve`, `changes:execute` |
| Assignment investigator | Explain unexpected outcomes | Distinguish match from selection, read evidence and priority, identify overrides, and compare history with audit | `employees:read`, `assignments:read`, `policies:read`, `audit:read` as needed |
| Access administrator | Manage human access | Create scoped roles and users, link accounts to employees, review privileged access, and understand policy-derived roles | `access:read`, `access:manage`, `access:review`, often `employees:read` |
| Signed-in reader | Learn vocabulary without task access | Understand concepts and recognize when an administrator is required | No feature permission beyond an authenticated session |

Machine API operators are a later reference audience. The backend supports
machine credentials and assignment queries, but the current frontend has no UI
for those workflows. Public marketing visitors are also out of scope because
`/learn` is intended for authenticated application users.

## The Avery Chen scenario

The course follows Avery Chen, a fictional employee joining Acme on September
14, 2026. The fixture is a documentation contract, not current demo data. Phase
3 examples and Phase 5 exercises should use an isolated workspace or resettable
fixture so they cannot change customer data.

### Employee and account

| Property | Value | Teaching purpose |
| --- | --- | --- |
| Name | Avery Chen | Matches the employee-form placeholder and does not collide with demo records |
| State or region | California | Demonstrates a direct geographic condition |
| Department | Engineering | Demonstrates a trusted employee fact |
| Employee type | Full-time | Demonstrates overlapping policy candidates |
| Work location | San Francisco | Shows the distinction between location and state |
| Start date | 2026-09-14 | Drives date and later tenure examples |
| Manager | Maya Patel | Introduces reporting relationships and derived organization fields |
| User account | `avery.chen@example.test`, linked after the employee exists | Makes clear that an employee record and a sign-in account are separate objects |

The `.test` address is reserved for examples. Never use a real email address in
course fixtures.

### Assignment fields

| Field | Cardinality | Why it is in the scenario |
| --- | --- | --- |
| Pay schedule | One | Makes priority selection visible |
| Vacation policy | One | Shows an ordinary single-value result |
| Application access | Many | Shows set-union behavior and group inheritance |
| Compliance training | Many | Shows location-specific accumulation |
| Equipment stipend | One | Gives the Engineering rule a non-access output |

Cardinality is fixed after field creation in the current interface. A `one`
field selects the highest-priority value; a `many` field retains unique values
from all matching policies.

### Policies and group

| Policy or group | Configuration | Expected effect for Avery |
| --- | --- | --- |
| US Employee Pay | Active; full-time; priority 10; Pay schedule = Semi-monthly | Matches but loses to the higher-priority California policy |
| California Pay Schedule | Active; state = California; priority 20; Pay schedule = Bi-weekly | Supplies the final pay schedule |
| Standard PTO | Active; full-time; priority 10; Vacation policy = Standard PTO | Supplies the vacation policy |
| California Compliance | Active; state = California; priority 30; Compliance training = CA Workplace Harassment | Adds a compliance assignment |
| Engineering Equipment | Active; department = Engineering; priority 10; Equipment stipend = $1,000 annual | Supplies the stipend directly |
| Security Baseline | Active; full-time; priority 5; Application access = 1Password | Adds one many-valued access result directly |
| Engineering group | Explicit membership; Engineering Access attached | Makes the attached policy a candidate without requiring its conditions to match |
| Engineering Access | Active; direct rule location = Remote; priority 10; Application access = GitHub and Linear; optional Engineering tools role | Avery does not match the direct rule, so the Engineering group supplies this policy and later demonstrates automated access |

Do not teach that group membership is computed from department. Groups are
explicit collections. A policy attached to a group applies to each member even
when its condition tree would not directly match that employee. Direct and
group origins are deduplicated before resolution.

### Expected current assignments

| Field | Final value or values | Reason |
| --- | --- | --- |
| Pay schedule | Bi-weekly | California Pay Schedule at priority 20 beats US Employee Pay at priority 10 |
| Vacation policy | Standard PTO | Standard PTO matches Avery's full-time employee type |
| Application access | 1Password, GitHub, Linear | A many-valued field combines unique results from a direct policy and a group policy |
| Compliance training | CA Workplace Harassment | California Compliance matches Avery's state |
| Equipment stipend | $1,000 annual | Engineering Equipment matches Avery's department |

### Story changes used later

1. **Onboarding:** preview and create Avery. This teaches that employee facts are
   inputs and assignments are resolved outputs.
2. **Group membership:** add Avery to Engineering and show GitHub and Linear as
   group-origin assignments.
3. **Priority:** compare both pay policies and explain why “matched” does not
   necessarily mean “selected.”
4. **Future version:** schedule California Pay Schedule version 2 to provide
   Weekly pay from October 1, 2026. The old open-ended version closes on
   September 30 because policy-version effective dates are inclusive.
5. **Preview and approval:** have a policy author preview a version of Engineering
   Access that grants the automation-eligible Engineering tools role. A distinct
   approver reviews, approves, and executes the exact request.
6. **Override:** temporarily override Avery's Pay schedule to Monthly, then remove
   the override and show the policy result returning.
7. **History and audit:** use assignment history to answer what value Avery had at
   a time, and the audit log to answer what changed and who caused it.

### Scenario invariants

- An override replaces all policy results for its field; it does not repair or
  conceal an equal-priority policy conflict.
- A user account receives an automated role only when it is linked to the
  matching employee. Explicit role assignments remain separate and are not
  removed by policy reconciliation.
- Policy effective ranges use inclusive dates. Assignment-history rows use
  half-open timestamps.
- Connected preview and execution behavior is authoritative. Demo-mode success
  messages are not persistence guarantees.
- Course screenshots must display fictional data only.
