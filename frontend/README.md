# PolicyOS frontend

PolicyOS is the role-aware interface for the policy assignment engine in this repository. It gives authorized users a dashboard, employee directory, assignment explanations, employee onboarding and editing with impact previews, policy authoring with effective dates and deterministic priorities, an independent change-approval queue, group management, manual overrides, assignment history, policy lifecycle controls, assignment-field setup, an inspectable audit log, human access administration, and an authenticated Fumadocs learning center at `/learn`.

Use **Command/Ctrl + K** anywhere in the app to open Quick Find and jump directly to a page or common action.

Learning content lives in `content/learn` as schema-validated MDX. The collection,
ordering, and metadata contract are defined in `lib/learn-source.ts`; the broader
curriculum and authoring workflow live in `../docs/learn`.

## Run locally

Configure the FastAPI backend URL before starting the frontend:

```dotenv
POLICY_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

```bash
cp .env.example .env.local
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). `POLICY_API_URL` is required; the frontend does not contain an offline data source or local mutation path. Directory filters and pagination are executed by the backend, employee form suggestions and audit facets come from backend reference endpoints, and both new-policy and new-version previews run through the backend policy engine.

The public homepage at `/` introduces PolicyOS. Visitors choose **Sign in** (`/login`) or **Sign up** (`/signup`); the workspace overview lives at `/dashboard`. When the workspace is uninitialized, sign up redirects to the one-time Root account setup at `/setup`. After initialization, the signup page directs people to their administrator for an account.

Root can create least-privilege roles and provision users under **Access control**. Each role combines action permissions with two independent data boundaries: employee visibility (`all`, reporting tree, linked employee, or none) and assignment-field access (`all`, selected fields, or none). This lets an IT administrator work only with Application Access while a payroll administrator works only with Pay Schedule, even when both can perform the same actions. Roles are assigned to and revoked from users only through explicit access-administration actions; policies produce employee assignments only. Policy drafting, version creation, activation, and archiving are separate grants. Human previews create approval requests, and the **Approvals** page enforces author/approver separation before the approving user executes the exact reviewed change. Policy responses supply record-specific capabilities so the interface does not duplicate lifecycle and scope decisions in React. User accounts can be linked to an employee record so self and reporting-tree scopes have a clear anchor. New users receive a temporary password and must replace it on first login. Navigation and mutation controls reflect effective role permissions, while connected data is filtered by the backend. Browser requests use the same-origin `/api/backend/*` proxy, and the backend session token remains in an HTTP-only cookie rather than client-side JavaScript.

## Checks

```bash
npm run lint
npm run build
```

The backend is the source of truth for all operational data, authentication, authorization, reference values, assignment resolution, reconciliation, approval tokens, readiness, and audit records. This includes the grouped state and territory catalog used by the searchable employee and policy inputs. The frontend owns presentation concerns such as labels, navigation, form state, and current-page display sorting.
