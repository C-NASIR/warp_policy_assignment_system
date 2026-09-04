# PolicyOS frontend

PolicyOS is the role-aware interface for the policy assignment engine in this repository. It gives authorized users a dashboard, employee directory, assignment explanations, employee onboarding and editing with impact previews, policy authoring with effective dates, deterministic priorities, and automated access roles, an independent change-approval queue, group management, manual overrides, assignment history, policy lifecycle controls, assignment-field setup, an inspectable audit log, and human access administration.

Use **Command/Ctrl + K** anywhere in the app to open Quick Find and jump directly to a page or common action.

## Run locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The interface starts in a complete demo mode when no API URL is configured. To connect it to the FastAPI backend, copy `.env.example` to `.env.local` and set:

```dotenv
POLICY_API_URL=http://127.0.0.1:8000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
```

On the first connected visit, PolicyOS opens the one-time Root account setup. Root can then create least-privilege roles and provision users under **Access control**. Each role combines action permissions with two independent data boundaries: employee visibility (`all`, reporting tree, linked employee, or none) and assignment-field access (`all`, selected fields, or none). This lets an IT administrator work only with Application Access while a payroll administrator works only with Pay Schedule, even when both can perform the same actions. Policy drafting, version creation, activation, and archiving are separate grants. Safe roles can opt into policy automation; a matching employee's linked account then receives the role without changing protected explicit assignments. Human previews create approval requests, and the **Approvals** page enforces author/approver separation before the approving user executes the exact reviewed change. Policy responses supply record-specific capabilities so the interface does not duplicate lifecycle and scope decisions in React. User accounts can be linked to an employee record so self and reporting-tree scopes have a clear anchor. New users receive a temporary password and must replace it on first login. Navigation and mutation controls reflect effective role permissions, while connected data is filtered by the backend. Browser requests use the same-origin `/api/backend/*` proxy, and the backend session token remains in an HTTP-only cookie rather than client-side JavaScript.

## Checks

```bash
npm run lint
npm run build
```

The backend remains the source of truth for authentication, assignment resolution, reconciliation, approval tokens, and audit records. Demo mode is intentionally non-persistent and exists so the frontend can be explored without provisioning Postgres.
