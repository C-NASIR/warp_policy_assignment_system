# Learn PolicyOS content map

This is the approved-ready baseline curriculum for `/learn`. The IDs are stable
and should become `content_id` values in MDX. Priority `P0` is required for the
first usable learning release, `P1` completes practical feature coverage, and
`P2` is useful depth after core workflows are reliable.

## Start here: ordered beginner course

| ID | Order | Article | Learner outcome | Scenario beat | Hands-on permissions | Priority |
| --- | ---: | --- | --- | --- | --- | --- |
| B01 | 10 | What PolicyOS does | Describe how workforce facts become explainable assignments | Meet Avery and see the final result before learning the parts | None | P0 |
| B02 | 20 | Employees and user accounts are different | Explain why Avery can exist without a login and why an account link matters | Create Avery's employee record, then introduce the separate account | None | P0 |
| B03 | 30 | Inputs, assignment fields, and values | Distinguish condition inputs from assignment outputs and `one` from `many` | Classify Avery's facts and five output fields | None | P0 |
| B04 | 40 | How policies match | Read direct conditions and explain explicit group inheritance | Match California policies and add Avery to Engineering | None | P0 |
| B05 | 50 | Effective dates, priority, and cardinality | Predict the active version and final value for both field types | Resolve Avery's two pay candidates and three access values | None | P0 |
| B06 | 60 | Why Avery received each assignment | Use an assignment explanation to trace source, origin, evidence, and selection | Open Avery's assignment cards | `employees:read`, `assignments:read` | P0 |
| B07 | 70 | Preview, approval, execution, and reconciliation | Distinguish a simulation, an approval decision, execution, and downstream recomputation | Preview an Engineering Access version and follow independent approval | Author: policy record capability and `changes:preview`; second user: `changes:approve`, then `changes:execute` | P0 |
| B08 | 80 | Overrides are explicit exceptions | Explain field replacement and how removing an override restores policy results | Temporarily set Avery's pay schedule to Monthly | `employees:read`, `assignments:read`, `assignments:manage`, `changes:preview` | P0 |
| B09 | 90 | History and audit answer different questions | Choose the correct record for “what was true?” versus “who changed it?” | Compare Avery's assignment history with the audit event | `employees:read`, `assignments:read`, optionally `audit:read` | P0 |
| B10 | 100 | Your first assignment walkthrough | Reconstruct Avery's complete assignment and pass a short knowledge check | Repeat the story from employee facts to evidence | None | P0 |

The beginner course is conceptual first. When a learner lacks a listed
permission, the lesson shows the expected fictional screen state and explains
which role can perform the optional in-product step.

## Core concepts

| ID | Article | Key question | Evidence owner | Priority |
| --- | --- | --- | --- | --- |
| C01 | Employee records versus user accounts | Why doesn't every employee sign in? | Access control | P0 |
| C02 | Condition fields versus assignment fields | Which data is an input and which is an output? | Policy engine | P0 |
| C03 | Policies, versions, and assignments | What is defined, versioned, and resolved? | Policy engine | P0 |
| C04 | Direct matches and group-inherited policies | How can a policy apply in more than one way? | Groups | P0 |
| C05 | Condition trees and derived facts | How do ALL, ANY, nesting, tenure, and reporting facts work? | Policy authoring | P1 |
| C06 | One-value and many-value resolution | When does priority select one result and when are values combined? | Assignment resolution | P0 |
| C07 | Equal-priority conflicts | Why does PolicyOS stop instead of picking arbitrarily? | Assignment resolution | P0 |
| C08 | Effective dates and version boundaries | Which version applies on a date? | Policy versions | P0 |
| C09 | Current, historical, and future results | Is the answer recorded or calculated? | Assignment queries | P1 |
| C10 | Reconciliation and scheduled changes | When are assignments recalculated? | Reconciliation | P1 |
| C11 | Manual overrides and provenance | What does an exception replace and what is retained? | Overrides | P0 |
| C12 | Preview, approval, and exact execution | What is simulated, authorized, and committed? | Change approvals | P0 |
| C13 | Assignment history versus the audit log | Which timeline answers my question? | Audit | P0 |
| C14 | Permissions and two data boundaries | Why can two people with the same action see different records or fields? | Access control | P1 |
| C15 | Explicit and policy-derived roles | How can a policy grant access without removing manual role assignments? | Automated access | P1 |

## How-to guides

| ID | Guide | Primary audience | Entry point | Required permission or capability | Priority |
| --- | --- | --- | --- | --- | --- |
| G01 | Onboard an employee and review assignments | People operator | `/employees/new` | `employees:create`, `changes:preview` | P0 |
| G02 | Change employee facts safely | People operator | `/employees/{id}` | `employees:update`, `changes:preview` | P0 |
| G03 | Investigate why an employee has a value | Assignment investigator | `/employees/{id}` | `employees:read`, `assignments:read` | P0 |
| G04 | Create an assignment field | Configuration admin | `/settings` | `settings:manage` | P1 |
| G05 | Create a policy | Policy author | `/policies/new` | `policies:create`, `settings:read` | P0 |
| G06 | Create and schedule a policy version | Policy author | `/policies/{id}` | Record `can_create_version` capability | P0 |
| G07 | Activate, archive, or reactivate a policy | Policy activator | `/policies/{id}` | Record `can_activate` or `can_archive` capability | P0 |
| G08 | Preview policy impact | Policy author | `/policies/new?policyId={id}` | `changes:preview` and policy record access | P0 |
| G09 | Create and manage a group | Group manager | `/groups` | `groups:create`, `groups:update` | P1 |
| G10 | Add or remove a group member | Group manager | `/groups/{id}` | `groups:update`, `changes:preview` | P0 |
| G11 | Attach or detach a policy from a group | Group manager | `/groups/{id}` | `groups:update` | P1 |
| G12 | Create, change, or remove an override | Assignment manager | `/employees/{id}` | `assignments:manage`, `changes:preview` | P0 |
| G13 | Review, approve, and execute a sensitive change | Approver | `/approvals` | Request capabilities plus `changes:approve` or `changes:execute` | P0 |
| G14 | Search and compare audit events | Auditor | `/audit` | `audit:read` | P1 |
| G15 | Create a least-privilege role | Access administrator | `/access` | `access:manage` | P1 |
| G16 | Provision and link a user account | Access administrator | `/access` | `access:manage`; `employees:read` to choose a visible employee | P1 |
| G17 | Review privileged access findings | Security reviewer | `/access/review` | `access:review` | P1 |
| G18 | Enroll MFA and manage sessions | Signed-in user | `/account/security` | Signed-in account; recent reauthentication for sensitive actions | P1 |

## Feature reference

| ID | Reference article | Coverage | Priority |
| --- | --- | --- | --- |
| R00 | Glossary | Employee, user, condition field, assignment field, policy, version, match, candidate, assignment, priority, effective date, group, override, preview, approval, reconciliation, history, and audit | P0 |
| R01 | Overview | Metrics, coverage, recent changes, and quick actions; flag currently static health copy | P1 |
| R02 | Employee directory | Search, filters, visible population, and Add employee capability | P1 |
| R03 | Employee detail | Profile, current assignments, explanations, health, overrides, and history | P0 |
| R04 | Policy builder | Basics, conditions, nested groups, outputs, automated roles, and impact panel | P0 |
| R05 | Policy detail and lifecycle | Current version, conditions, values, impact terms, history, and record capabilities | P0 |
| R06 | Groups | Explicit membership, attached policies, previewed membership, and immediate attachment changes | P1 |
| R07 | Change approvals | Statuses, impact, exact payload, author/approver separation, expiry, and execution | P0 |
| R08 | Assignment fields | Cardinality, fixed-after-create behavior, and resolution labels | P1 |
| R09 | Audit log | Filters, entity labels, summaries, UTC timestamps, and payloads | P1 |
| R10 | Access control | Users, roles, permissions, employee scope, assignment-field scope, and automation eligibility | P1 |
| R11 | Access review | Finding types and remediation destinations | P2 |
| R12 | Account security | Password, MFA, recovery codes, reauthentication, sessions, and events | P1 |
| R13 | Quick Find | Keyboard access, searchable pages and actions, and permission filtering | P1 |
| R14 | Permission catalog | Every human permission and the distinction between action permission and data scope | P1 |
| R15 | Condition field catalog | Static and derived fields, operators, input types, and dependencies | P1 |
| R16 | Policy status and record-capability matrix | Draft, active, archived, versioning, activation, and archive combinations | P1 |
| R17 | Assignment explanation anatomy | Policy/version, origin, matched clauses, strategy, candidates, and override replacement | P0 |

## Troubleshooting

| ID | Article | Diagnostic path | Priority |
| --- | --- | --- | --- |
| T01 | Why didn't this policy apply? | Check policy status, effective version, direct conditions, group attachment and membership, then field scope | P0 |
| T02 | The policy matched, so why didn't it supply the assignment? | Compare cardinality, priority, competing candidates, and overrides | P0 |
| T03 | PolicyOS reports an equal-priority conflict | Find different values on a `one` field, change priority or rule overlap, and preview again | P0 |
| T04 | Why hasn't a future version taken effect? | Check inclusive dates, gaps, policy status, scheduler operation, and current-versus-future query mode | P0 |
| T05 | Why is a policy value hidden by an override? | Inspect field-level overrides and remove only after previewing the restored result | P0 |
| T06 | Why can't I see this employee, policy, or assignment field? | Check action permission, employee scope, assignment-field scope, account link, and non-disclosing 404 behavior | P0 |
| T07 | Why can't I approve or execute this request? | Check authorship separation, approver identity, request status, expiry, and required permissions | P0 |
| T08 | The approved change is stale or expired | Re-preview current state and obtain a new approval; never reuse altered input | P1 |
| T09 | Why did a group policy apply when its conditions did not match? | Explain explicit group attachment semantics | P1 |
| T10 | Why did removing a group or policy change assignments immediately? | Trace affected members through synchronous reconciliation | P1 |
| T11 | Why did the value stay the same but history gained a row? | Check source or material explanation changes | P1 |
| T12 | Why are demo changes gone after refresh? | Explain non-persistence and simplified demo previews | P1 |
| T13 | Why can't I add another value to a one-value field? | Check field cardinality and existing active override | P2 |
| T14 | Why is a past policy-impact request unavailable? | Explain that historical employee facts are not versioned; use assignment history for recorded outcomes | P2 |

## Cross-links for the beginner journey

Each beginner lesson should end with no more than three links:

- the next lesson in order;
- one concept article that explains the mechanism in more depth;
- one permission-aware guide for doing the task.

The final walkthrough links to T01, T02, and G03 so the learner moves naturally
from instruction to independent investigation.

## Publication waves

| Wave | Scope | Exit condition |
| --- | --- | --- |
| Phase 2 samples | One short sample in each of Start here, Concepts, Guides, Reference, and Troubleshooting | Navigation, metadata, responsive layout, and access behavior validated |
| Phase 3 first usable release | B01-B10 plus all P0 concept articles and the glossary terms they require | A novice can explain Avery's assignment from facts to final result |
| Phase 4 practical coverage | All P0/P1 guides, references, and troubleshooting articles | Every major visible workflow has a task guide and diagnostic route |
| Later depth | P2 articles, isolated exercises, progress, feedback, and optional AI assistance | Added only after written content and search are trustworthy |

## Content-map approval checklist

Product and feature owners should confirm:

- the audience names match how PolicyOS is sold and administered;
- the Avery fixture is safe to standardize across docs and exercises;
- no P0 workflow is missing;
- permission requirements match intended role design;
- the first usable release boundary is B01-B10 plus P0 concepts;
- API-only workflows remain outside the initial UI learning promise.
