# PolicyOS frontend

PolicyOS is the admin interface for the policy assignment engine in this repository. It gives company admins a dashboard, employee directory, assignment explanations, employee onboarding and editing with impact previews, policy authoring with effective dates and deterministic priorities, group management, manual overrides, assignment history, policy lifecycle controls, assignment-field setup, and an inspectable audit log.

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

On the first connected visit, PolicyOS opens the one-time Root account setup. Later visits require that human account to sign in. Browser requests use the same-origin `/api/backend/*` proxy, and the backend session token remains in an HTTP-only cookie rather than client-side JavaScript.

## Checks

```bash
npm run lint
npm run build
```

The backend remains the source of truth for authentication, assignment resolution, reconciliation, approval tokens, and audit records. Demo mode is intentionally non-persistent and exists so the frontend can be explored without provisioning Postgres.
