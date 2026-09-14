# Learner audiences and shared scenario

## Audience model

PolicyOS is an administrative assignment system with scoped user access. It does not provide a separate employee self-service portal. The learning center organizes material by the job a signed-in operator needs to do while keeping Concepts readable by anyone.

| Audience | Primary need | Must be able to explain or do | Typical permissions |
| --- | --- | --- | --- |
| New operator | Understand the system before changing data | Explain why an employee received a value and how application access is delegated | `employees:read`, `assignments:read`, sometimes `policies:read` and `groups:read` |
| People operator | Onboard and maintain employee facts safely | Preview assignment effects, save an employee change, and recognize downstream reconciliation | `employees:read`, `employees:create`, `employees:update`, `assignments:read`, `changes:preview` |
| Policy author | Define workforce rules | Choose conditions and outputs, set effective dates and priority, preview impact, and propose versions | `policies:read`, `policies:create`, `policies:version:create`, `settings:read`, `changes:preview`; active-policy versions also require activation authority |
| Policy activator | Control production policy behavior | Activate or archive policies and authorize versions without conflating authorship and activation | `policies:activate`, `policies:archive` |
| Group manager | Maintain explicit populations | Add or remove members, attach policies, and predict reconciliation | `groups:read`, `groups:create`, `groups:update`, plus related read permissions |
| Reviewer | Review supported sensitive changes independently | Inspect the exact request and impact, approve or reject another author's proposal, and execute an approved request | `changes:approve`, `changes:execute`, plus the policy authority needed by the change |
| Assignment investigator | Explain unexpected outcomes | Distinguish match from selection, read evidence and priority, identify overrides, and compare history with audit | `employees:read`, `assignments:read`, `policies:read`, `audit:read` as needed |
| Access administrator | Manage human access | Create scoped roles and users, link accounts to employees, assign roles explicitly, and review privileged access | `access:read`, `access:manage`, `access:review`, often `employees:read` |
| Scoped reader | Read only an allowed population or assignment domain | Explain why action permissions, employee scope, and assignment-field scope must all line up | Appropriate read permissions plus configured scopes |

These permission sets are illustrative, not built-in roles. Machine API operators remain a later reference audience; the current frontend has no UI for machine credentials and assignment queries.

## The growing company scenario

The curriculum uses one fictional company and recurring people. The names define teaching roles, not seeded accounts or promises about built-in access.

| Person | Employee record | PolicyOS user | Purpose in the story |
| --- | --- | --- | --- |
| Root operator | Not required | Initial Root account | Starts the empty workspace and establishes access for others |
| Rachel | Yes | Added and linked later | First employee, later a manager and scoped reader whose facts drive policy results |
| Morgan | Yes if the company records Morgan as an employee; the link is optional for all-employee scope | Added by Root | People operator and later policy author |
| Jordan | Optional | Added by an access administrator | Independent reviewer and executor for supported policy proposals |
| Devon | Yes; reports to Rachel | Not required | Rachel's direct report |
| Sam | Yes; reports to Devon | Not required | Rachel's indirect report |

Use reserved `.test` email addresses in fixtures. Never use a real address in course data.

## Organizational story contract

1. An empty workspace creates exactly one initial Root user. Root has wildcard authority and unrestricted employee and assignment-field visibility, but still follows authentication, configured security checks, domain validation, and applicable preview/execution contracts.
2. Rachel's employee record exists before any account for Rachel. Creating an employee never creates a user or grants application access.
3. Root gives Morgan a user account and an explicitly assigned People operator role. The example role is configured by the company; it is not built in.
4. Permissions define actions. Employee and assignment-field scopes independently define which data those actions may reach. Multiple roles broaden effective access.
5. Rachel's reporting-tree access includes Rachel, direct report Devon, and indirect report Sam only because Rachel's account is linked and an assigned role supplies both the read permissions and reporting-tree scope.
6. Rachel can instead receive a limited view of her own record through the same application when a linked account has suitable read permissions, self scope, and the intended field scope.
7. Morgan proposes a policy version. Jordan uses a separate account to inspect, approve or reject, and ordinarily execute the exact supported request. PolicyOS has no arbitrary reviewer assignment, built-in handoff message, or general approval fallback for every mutation.
8. User roles are assigned and revoked only through explicit access administration. Policy eligibility and employee reconciliation never change application access.

## Assignment scenario

The policy story uses Rachel's employee facts and these assignment fields:

| Field | Cardinality | Teaching purpose |
| --- | --- | --- |
| Pay schedule | One | Priority selection |
| Annual vacation allowance | One | Ordinary policy output, override, and future-version examples |
| Application access | Many | Set union and group-origin assignments |

Product Launch remains an explicit employee group. It is not populated from a department, does not define reporting relationships, and does not grant PolicyOS authority. A policy attached to it becomes a candidate for each explicit member.

## Verification invariants

- User roles are assigned and revoked explicitly; policies never change a user's roles.
- Scopes from all assigned roles are unioned. A narrow role cannot deny a broader grant.
- Reporting-tree scope includes the linked employee plus direct and indirect descendants. Being recorded as a manager does not create an account, permission, or role.
- Ordinary human lifecycle previews create independent approval requests. Policy creation and policy-version previews return display-only assignment summaries, while Root retains the privileged direct path.
- Approval alone commits nothing. The ordinary approving user executes; Root may execute an approved request. Stale or expired approvals require a fresh preview and review.
- Future effective dates still govern future policy behavior after execution, and scheduled reconciliation remains a deployment responsibility.
- Course screenshots and training fixtures use fictional data; application state still comes from the configured backend.
