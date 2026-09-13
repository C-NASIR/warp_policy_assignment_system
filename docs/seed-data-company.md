# Cedar Harbor Wind Systems seed company

The persistent test seed represents **Cedar Harbor Wind Systems**, a fictional
Chicago-based company that inspects, maintains, and analyzes utility-scale wind
turbines across the Great Lakes and central United States. Nothing in this
dataset represents a real person, company, credential, or operating environment.

## The company

Cedar Harbor combines a software organization with a distributed field-service
operation. Engineering builds fleet-health and inspection products. Field
Operations sends certified technicians to wind sites and service depots. Sales
and Customer Success work with utilities and asset owners. People Operations
administers employment and compliance programs from the Chicago headquarters.

Nadia Okafor is the CEO. Marcus Li runs Operations, Elliot Park leads
Engineering and Product, Elena Torres leads People Operations, and Simone
Laurent leads Revenue. Their teams form a multi-level reporting tree across
Illinois, Wisconsin, Texas, Colorado, Michigan, New York, Massachusetts, and
Washington. The population includes full-time, part-time, and contractor
workers, recent hires, long-tenured employees, individual contributors, and
managers.

## What is represented

The seed creates 25 employees, 12 human accounts, 10 roles, 8 employee groups,
8 assignment fields, and 15 policies. The records are intentionally connected:

- full-time and contractor baselines establish benefits, payroll, equipment,
  applications, training, expense limits, and information-access levels;
- higher-priority state, department, manager, executive, and tenure policies
  demonstrate deterministic conflict resolution;
- Incident Response and Blade Inspection policies arrive through group
  membership and show group origins in assignment explanations;
- all user roles are assigned explicitly and remain independent of policy results;
- a revised full-time package creates real assignment history, and a scheduled
  manager-policy version demonstrates a future effective date;
- active and retired overrides document approved exceptions for expenses,
  physical access, and contractor hardware;
- active, draft, and archived policies exercise the complete lifecycle;
- pending, rejected, executed, and expired approval requests populate the
  approval workflow;
- expired and revoked sessions, acknowledged security events, active and
  revoked API credentials, scheduled reconciliations, and a substantial audit
  trail make operational views useful.

Employee start dates and policy boundaries are generated relative to the day the
seed runs. Consequently, tenure and future-schedule examples remain meaningful
instead of aging out. The optional `--reference-date` argument fixes that anchor
when a deterministic fixture is needed.

## Suggested exploration

Start as Nadia to see the complete workspace. MFA is intentionally not
preconfigured; enroll it from account security before attempting a privileged
write. Then compare these accounts:

1. Priya Raman can author and preview policies across the company but cannot
   activate one.
2. Marcus Li can independently approve and execute another person's request.
3. Elena Torres can manage employees but sees only HR assignment domains.
4. Rafael Morales and Amara Nwosu see their own reporting trees and selected
   operational domains.
5. Renee Wallace has company-wide read-only audit and access-review visibility.
6. Kai Chen sees only himself through the explicitly assigned Employee Self
   Service role.
7. Luca Romano shows contractor rules and a hardware override. The approval
   queue also contains a pending leadership-cohort membership request for Imani
   Reed that is safe to approve and execute during testing.

Useful records to inspect include the two versions of **Core Full-time Employee
Package**, the future version of **People Manager Responsibilities**, the group
origin on **Incident Response Duty**, Priya's current and retired travel
exceptions, Mia's high travel exception, and **Archived VPN Access**.

## Loading the seed

From the repository root, run:

```bash
./scripts/load_test_data.sh
```

This creates the disposable `policy_assignments_demo` database when it does not
exist and loads the complete company dataset.

To run the backend against it, set `DATABASE_MODE=demo` in `backend/.env`. Set
the mode back to `real` to use `DATABASE_URL`; the demo and real URLs are stored
separately.

For a fixed timeline:

```bash
./scripts/load_test_data.sh --reference-date 2026-09-06
```

To use another existing testing database:

```bash
./scripts/load_test_data.sh \
  --database-url postgresql+psycopg:///my_policyos_test_database
```

The command creates missing tables and commits the entire dataset atomically. It
refuses to run when tenant data is already present, preventing fictional records
from being mixed into an existing workspace. Re-running it after this exact seed
has completed reports the existing seed without duplicating records.

Configure the frontend's `POLICY_API_URL` for the backend connected to this
database, then use the accounts in [seed-data-credentials.txt](seed-data-credentials.txt).

## Testing-only boundary

This seed must never be loaded into production or a database containing customer
data. The reserved `.example` email domain, plaintext credential file, predictable API token,
and fictional history are designed only for local development, QA, screenshots,
training, and automated tests.
