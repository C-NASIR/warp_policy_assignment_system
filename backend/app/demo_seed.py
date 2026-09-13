"""A coherent, test-only company dataset for local PolicyOS evaluation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    APICredential,
    ApprovedChangeExecution,
    AssignmentFieldDefinition,
    AuditLog,
    AuthSession,
    ChangeApprovalRequest,
    Employee,
    EmployeeAssignment,
    EmployeeGroupMembership,
    EmployeeOverride,
    Group,
    GroupPolicy,
    Policy,
    Role,
    ScheduledReconciliation,
    SecurityEvent,
    User,
)
from app.schemas import (
    ChangePreviewRead,
    ConditionCreate,
    ConditionGroupCreate,
    GroupMembershipChangePreview,
    PolicyValueCreate,
    PolicyVersionCreate,
)
from app.services.access_control import create_role, create_user
from app.services.audit import record_audit_log, snapshot_entity
from app.services.auth import hash_token
from app.services.change_approvals import (
    change_digest,
    change_precondition_digest,
    preview_digest,
)
from app.services.human_auth import hash_session_token
from app.services.policy_authoring import create_policy_version_from_input
from app.services.reconciliation import reconcile_employees
from app.services.scheduled_reconciliations import sync_policy_version_schedules

COMPANY_NAME = "Cedar Harbor Wind Systems"
SEED_ROOT_EMAIL = "nadia.okafor@cedarharbor.example"
READ_ONLY_API_TOKEN = "wpa_seed_cedar_harbor_readonly_2026_example_token"

TEST_USERS: tuple[dict[str, Any], ...] = (
    {
        "key": "nadia",
        "name": "Nadia Okafor",
        "email": SEED_ROOT_EMAIL,
        "password": "HarborRoot!2026",
        "root": True,
        "employee": "nadia",
    },
    {
        "key": "elliot",
        "name": "Elliot Park",
        "email": "elliot.park@cedarharbor.example",
        "password": "TurbineAdmin!26",
        "roles": ["Platform Administrator"],
        "employee": "elliot",
    },
    {
        "key": "priya",
        "name": "Priya Raman",
        "email": "priya.raman@cedarharbor.example",
        "password": "PolicyAuthor!26",
        "roles": ["Policy Author"],
        "employee": "priya",
    },
    {
        "key": "marcus",
        "name": "Marcus Li",
        "email": "marcus.li@cedarharbor.example",
        "password": "ApproveWind!26",
        "roles": ["Change Approver"],
        "employee": "marcus",
    },
    {
        "key": "elena",
        "name": "Elena Torres",
        "email": "elena.torres@cedarharbor.example",
        "password": "PeopleOpsWind!26",
        "roles": ["People Operations"],
        "employee": "elena",
    },
    {
        "key": "rafael",
        "name": "Rafael Morales",
        "email": "rafael.morales@cedarharbor.example",
        "password": "FieldOpsWind!26",
        "roles": ["Department Manager"],
        "employee": "rafael",
    },
    {
        "key": "renee",
        "name": "Renee Wallace",
        "email": "renee.wallace@cedarharbor.example",
        "password": "AuditHarbor!26",
        "roles": ["Compliance Auditor"],
        "employee": "renee",
    },
    {
        "key": "amara",
        "name": "Amara Nwosu",
        "email": "amara.nwosu@cedarharbor.example",
        "password": "ManageEngWind!26",
        "roles": ["Department Manager"],
        "employee": "amara",
    },
    {
        "key": "kai",
        "name": "Kai Chen",
        "email": "kai.chen@cedarharbor.example",
        "password": "EngineerWind!26",
        "roles": ["Employee Self Service"],
        "employee": "kai",
    },
    {
        "key": "luca",
        "name": "Luca Romano",
        "email": "luca.romano@cedarharbor.example",
        "password": "ContractorWind!26",
        "roles": ["Contractor Self Service"],
        "employee": "luca",
    },
    {
        "key": "kendra",
        "name": "Kendra Shaw",
        "email": "kendra.shaw@cedarharbor.example",
        "password": "SuspendedDemo!26",
        "roles": ["Compliance Auditor"],
        "status": "suspended",
    },
    {
        "key": "beau",
        "name": "Beau Martin",
        "email": "beau.martin@cedarharbor.example",
        "password": "DisabledDemo!26",
        "roles": ["Employee Self Service"],
        "status": "disabled",
    },
)


@dataclass(frozen=True)
class SeedSummary:
    company: str
    employees: int
    users: int
    roles: int
    groups: int
    policies: int
    assignments: int
    audit_logs: int


def seed_demo_company(
    session: Session, *, reference_time: datetime | None = None
) -> SeedSummary:
    """Populate an otherwise fresh database in one transaction.

    The system condition-field catalog may already exist. Any tenant/business data
    causes a refusal so this helper can never merge fictional records into a real
    workspace. Calling it again after a complete seed is harmless.
    """
    now = (reference_time or datetime.now(UTC)).astimezone(UTC).replace(microsecond=0)
    existing_users = session.scalar(select(func.count(User.id))) or 0
    if existing_users and session.scalar(
        select(User.id).where(User.email == SEED_ROOT_EMAIL)
    ):
        return _summary(session)
    populated = {
        "users": existing_users,
        "employees": session.scalar(select(func.count(Employee.id))) or 0,
        "policies": session.scalar(select(func.count(Policy.id))) or 0,
        "groups": session.scalar(select(func.count(Group.id))) or 0,
        "roles": session.scalar(select(func.count(Role.id))) or 0,
        "assignment fields": session.scalar(
            select(func.count(AssignmentFieldDefinition.id))
        )
        or 0,
        "assignments": session.scalar(
            select(func.count()).select_from(EmployeeAssignment)
        )
        or 0,
        "overrides": session.scalar(select(func.count()).select_from(EmployeeOverride))
        or 0,
        "API credentials": session.scalar(
            select(func.count()).select_from(APICredential)
        )
        or 0,
        "audit logs": session.scalar(select(func.count()).select_from(AuditLog)) or 0,
        "approval requests": session.scalar(
            select(func.count()).select_from(ChangeApprovalRequest)
        )
        or 0,
        "scheduled reconciliations": session.scalar(
            select(func.count()).select_from(ScheduledReconciliation)
        )
        or 0,
    }
    nonempty = [f"{name}={count}" for name, count in populated.items() if count]
    if nonempty:
        raise RuntimeError(
            "Refusing to seed a database that already contains tenant data ("
            + ", ".join(nonempty)
            + "). Use a fresh testing database."
        )

    fields = _create_assignment_fields(session)
    employees = _create_employees(session, now.date())
    groups = _create_groups(session, employees)
    roles = _create_roles(session, fields, now)
    users = _create_users(session, employees, roles, now)
    policies = _create_policies(session, fields, roles, now)
    _attach_group_policies(session, groups, policies)

    historical_at = now - timedelta(days=300)
    historical_employee_ids = [
        employee.id
        for employee in employees.values()
        if employee.start_date <= historical_at.date()
    ]
    reconcile_employees(
        session,
        historical_employee_ids,
        reconciliation_at=historical_at,
        actor="system",
    )

    _create_overrides(session, employees, fields, now)
    reconcile_employees(
        session,
        [employee.id for employee in employees.values()],
        reconciliation_at=now,
        actor="system",
    )
    _create_auth_history(session, users, now)
    _create_api_credentials(session, now)
    _create_approval_history(session, users, employees, groups, fields, policies, now)
    _create_operational_history(session, users, employees, policies, now)
    _create_schedule_history(session, policies, now)
    session.flush()
    return _summary(session)


def _create_assignment_fields(session: Session) -> dict[str, AssignmentFieldDefinition]:
    specs = (
        ("Pay Schedule", "one"),
        ("Benefits Plan", "one"),
        ("Laptop Profile", "one"),
        ("Application Access", "many"),
        ("Facility Access", "many"),
        ("Compliance Training", "many"),
        ("Travel Approval Limit", "one"),
        ("Data Classification", "one"),
        ("Safety Equipment", "many"),
        ("On-call Rotation", "one"),
    )
    result = {
        name: AssignmentFieldDefinition(
            field=name, cardinality=cardinality, conflict_resolution="priority"
        )
        for name, cardinality in specs
    }
    session.add_all(result.values())
    session.flush()
    return result


def _create_employees(session: Session, today: date) -> dict[str, Employee]:
    specs = (
        (
            "nadia",
            "Nadia Okafor",
            "Illinois",
            "Executive",
            "Full-time",
            "Chicago HQ",
            2900,
            None,
        ),
        (
            "marcus",
            "Marcus Li",
            "Illinois",
            "Operations",
            "Full-time",
            "Chicago HQ",
            2400,
            "nadia",
        ),
        (
            "elliot",
            "Elliot Park",
            "Illinois",
            "Engineering",
            "Full-time",
            "Chicago HQ",
            2300,
            "nadia",
        ),
        (
            "elena",
            "Elena Torres",
            "Illinois",
            "People Operations",
            "Full-time",
            "Chicago HQ",
            2100,
            "nadia",
        ),
        (
            "simone",
            "Simone Laurent",
            "Illinois",
            "Revenue",
            "Full-time",
            "Chicago HQ",
            1850,
            "nadia",
        ),
        (
            "rafael",
            "Rafael Morales",
            "Wisconsin",
            "Field Operations",
            "Full-time",
            "Milwaukee Service Hub",
            1800,
            "marcus",
        ),
        (
            "renee",
            "Renee Wallace",
            "Wisconsin",
            "Field Operations",
            "Full-time",
            "Milwaukee Service Hub",
            1420,
            "rafael",
        ),
        (
            "amara",
            "Amara Nwosu",
            "Illinois",
            "Engineering",
            "Full-time",
            "Chicago HQ",
            1510,
            "elliot",
        ),
        (
            "devin",
            "Devin Brooks",
            "Illinois",
            "Product",
            "Full-time",
            "Chicago HQ",
            1320,
            "elliot",
        ),
        (
            "priya",
            "Priya Raman",
            "Illinois",
            "Engineering",
            "Full-time",
            "Chicago HQ",
            1190,
            "amara",
        ),
        (
            "kai",
            "Kai Chen",
            "Texas",
            "Engineering",
            "Full-time",
            "Remote - Austin",
            970,
            "amara",
        ),
        (
            "lila",
            "Lila Ahmed",
            "Washington",
            "Engineering",
            "Full-time",
            "Remote - Seattle",
            610,
            "amara",
        ),
        (
            "jonah",
            "Jonah Brooks",
            "Massachusetts",
            "Engineering",
            "Full-time",
            "Remote - Boston",
            170,
            "amara",
        ),
        (
            "tessa",
            "Tessa Nguyen",
            "Illinois",
            "Product",
            "Full-time",
            "Chicago HQ",
            740,
            "devin",
        ),
        (
            "imani",
            "Imani Reed",
            "Illinois",
            "People Operations",
            "Full-time",
            "Chicago HQ",
            880,
            "elena",
        ),
        (
            "caleb",
            "Caleb Foster",
            "Illinois",
            "People Operations",
            "Part-time",
            "Chicago HQ",
            460,
            "elena",
        ),
        (
            "sonya",
            "Sonya Patel",
            "Texas",
            "Sales",
            "Full-time",
            "Austin Sales Office",
            1260,
            "simone",
        ),
        (
            "omar",
            "Omar Haddad",
            "Texas",
            "Sales",
            "Full-time",
            "Austin Sales Office",
            520,
            "sonya",
        ),
        (
            "mia",
            "Mia Thompson",
            "New York",
            "Sales",
            "Full-time",
            "Remote - New York",
            260,
            "sonya",
        ),
        (
            "jae",
            "Jae Park",
            "Michigan",
            "Customer Success",
            "Full-time",
            "Remote - Detroit",
            690,
            "simone",
        ),
        (
            "jordan",
            "Jordan Kim",
            "Wisconsin",
            "Field Operations",
            "Full-time",
            "Milwaukee Service Hub",
            1020,
            "renee",
        ),
        (
            "aiden",
            "Aiden Murphy",
            "Texas",
            "Field Operations",
            "Full-time",
            "Abilene Field Depot",
            790,
            "renee",
        ),
        (
            "mateo",
            "Mateo Garcia",
            "Colorado",
            "Field Operations",
            "Full-time",
            "Remote - Denver",
            80,
            "renee",
        ),
        (
            "luca",
            "Luca Romano",
            "Illinois",
            "Engineering",
            "Contractor",
            "Chicago HQ",
            215,
            "amara",
        ),
        (
            "ana",
            "Ana Silva",
            "Wisconsin",
            "Field Operations",
            "Contractor",
            "Milwaukee Service Hub",
            125,
            "renee",
        ),
    )
    employees: dict[str, Employee] = {}
    for (
        key,
        name,
        state,
        department,
        employee_type,
        location,
        tenure_days,
        manager_key,
    ) in specs:
        employee = Employee(
            name=name,
            state=state,
            department=department,
            employee_type=employee_type,
            location=location,
            start_date=today - timedelta(days=tenure_days),
            manager=employees.get(manager_key),
        )
        session.add(employee)
        session.flush()
        employees[key] = employee
    return employees


def _create_groups(
    session: Session, employees: dict[str, Employee]
) -> dict[str, Group]:
    memberships = {
        "Engineering & Product": [
            "elliot",
            "amara",
            "devin",
            "priya",
            "kai",
            "lila",
            "jonah",
            "tessa",
            "luca",
        ],
        "Field Operations": ["rafael", "renee", "jordan", "aiden", "mateo", "ana"],
        "Incident Response": ["amara", "kai", "renee", "jordan", "aiden"],
        "People Managers": [
            "nadia",
            "marcus",
            "elliot",
            "elena",
            "simone",
            "rafael",
            "renee",
            "amara",
            "devin",
            "sonya",
        ],
        "Chicago HQ": [
            "nadia",
            "marcus",
            "elliot",
            "elena",
            "simone",
            "amara",
            "devin",
            "priya",
            "tessa",
            "imani",
            "caleb",
            "luca",
        ],
        "Customer-facing": ["simone", "sonya", "omar", "mia", "jae"],
        "Blade Inspection Certified": ["rafael", "renee", "jordan", "aiden", "ana"],
        "Contractors": ["luca", "ana"],
    }
    groups = {name: Group(name=name) for name in memberships}
    session.add_all(groups.values())
    session.flush()
    session.add_all(
        EmployeeGroupMembership(employee_id=employees[key].id, group_id=groups[name].id)
        for name, keys in memberships.items()
        for key in keys
    )
    session.flush()
    return groups


def _create_roles(
    session: Session, fields: dict[str, AssignmentFieldDefinition], now: datetime
) -> dict[str, Role]:
    field_ids = {name: field.id for name, field in fields.items()}
    specs = (
        (
            "Platform Administrator",
            "Runs PolicyOS configuration and access operations.",
            [
                "employees:read",
                "employees:create",
                "employees:update",
                "employees:delete",
                "policies:read",
                "policies:create",
                "policies:version:create",
                "policies:activate",
                "policies:archive",
                "groups:read",
                "groups:create",
                "groups:update",
                "assignments:read",
                "assignments:manage",
                "settings:read",
                "settings:manage",
                "audit:read",
                "access:read",
                "access:review",
                "access:manage",
                "api_credentials:manage",
                "changes:preview",
                "changes:execute",
                "changes:approve",
            ],
            "all",
            "all",
            [],
        ),
        (
            "Policy Author",
            "Designs and previews workforce policies but cannot activate them.",
            [
                "employees:read",
                "policies:read",
                "policies:create",
                "policies:version:create",
                "groups:read",
                "assignments:read",
                "settings:read",
                "changes:preview",
            ],
            "all",
            "all",
            [],
        ),
        (
            "Change Approver",
            "Independently reviews, approves, and executes sensitive changes.",
            [
                "employees:read",
                "policies:read",
                "groups:read",
                "assignments:read",
                "audit:read",
                "changes:approve",
                "changes:execute",
            ],
            "all",
            "all",
            [],
        ),
        (
            "People Operations",
            "Manages the workforce and HR-related assignment domains.",
            [
                "employees:read",
                "employees:create",
                "employees:update",
                "groups:read",
                "assignments:read",
                "assignments:manage",
                "settings:read",
                "changes:preview",
            ],
            "all",
            "selected",
            [
                field_ids["Pay Schedule"],
                field_ids["Benefits Plan"],
                field_ids["Compliance Training"],
            ],
        ),
        (
            "Department Manager",
            "Views a reporting tree and its operational assignments.",
            [
                "employees:read",
                "policies:read",
                "groups:read",
                "assignments:read",
                "changes:preview",
            ],
            "reporting_tree",
            "selected",
            [
                field_ids["Laptop Profile"],
                field_ids["Application Access"],
                field_ids["Facility Access"],
                field_ids["Travel Approval Limit"],
                field_ids["Safety Equipment"],
                field_ids["On-call Rotation"],
            ],
        ),
        (
            "Compliance Auditor",
            "Read-only company-wide access to policy decisions and audit evidence.",
            [
                "employees:read",
                "policies:read",
                "groups:read",
                "assignments:read",
                "settings:read",
                "audit:read",
                "access:read",
                "access:review",
            ],
            "all",
            "all",
            [],
        ),
        (
            "Employee Self Service",
            "Lets an employee inspect their own workplace access.",
            ["employees:read", "assignments:read"],
            "self",
            "selected",
            [
                field_ids["Benefits Plan"],
                field_ids["Laptop Profile"],
                field_ids["Application Access"],
                field_ids["Compliance Training"],
            ],
        ),
        (
            "Contractor Self Service",
            "Limited self-service access for contingent workers.",
            ["employees:read", "assignments:read"],
            "self",
            "selected",
            [
                field_ids["Laptop Profile"],
                field_ids["Application Access"],
                field_ids["Facility Access"],
                field_ids["Compliance Training"],
            ],
        ),
        (
            "Engineering Workspace",
            "Access to engineering assignment details.",
            ["employees:read", "policies:read", "assignments:read"],
            "self",
            "selected",
            [field_ids["Application Access"], field_ids["Data Classification"]],
        ),
        (
            "Incident Responder",
            "Visibility for on-call responders.",
            ["employees:read", "assignments:read"],
            "self",
            "selected",
            [field_ids["Application Access"], field_ids["On-call Rotation"]],
        ),
    )
    roles: dict[str, Role] = {}
    for index, (
        name,
        description,
        permissions,
        employee_scope,
        field_scope,
        selected_ids,
    ) in enumerate(specs):
        before_id = _max_audit_id(session)
        role = create_role(
            session,
            name=name,
            description=description,
            permissions=permissions,
            employee_scope=employee_scope,
            assignment_field_scope=field_scope,
            assignment_field_ids=selected_ids,
            actor="nadia.okafor@cedarharbor.example",
        )
        created_at = now - timedelta(days=620 - index * 7)
        role.created_at = role.updated_at = created_at
        _backdate_audits(session, before_id, created_at)
        roles[name] = role
    return roles


def _create_users(
    session: Session,
    employees: dict[str, Employee],
    roles: dict[str, Role],
    now: datetime,
) -> dict[str, User]:
    users: dict[str, User] = {}
    root_spec = TEST_USERS[0]
    root = User(
        name=root_spec["name"],
        email=root_spec["email"],
        password_hash=_password_hash(root_spec["password"]),
        status="active",
        is_root=True,
        password_change_required=False,
        employee_id=employees[root_spec["employee"]].id,
        created_at=now - timedelta(days=640),
        updated_at=now - timedelta(days=45),
        password_changed_at=now - timedelta(days=45),
        last_login_at=now - timedelta(days=2),
    )
    session.add(root)
    session.flush()
    users[root_spec["key"]] = root
    record_audit_log(
        session,
        actor=root.email,
        entity_type="User",
        entity_id=root.id,
        action="root_created",
        before=None,
        after={"email": root.email, "name": root.name, "is_root": True},
        timestamp=root.created_at,
    )

    for index, spec in enumerate(TEST_USERS[1:], start=1):
        before_id = _max_audit_id(session)
        user = create_user(
            session,
            name=spec["name"],
            email=spec["email"],
            password=spec["password"],
            role_ids=[roles[name].id for name in spec["roles"]],
            employee_id=employees[spec["employee"]].id
            if spec.get("employee")
            else None,
            actor=root.email,
        )
        created_at = now - timedelta(days=600 - index * 19)
        user.created_at = user.updated_at = created_at
        user.password_changed_at = created_at
        user.password_change_required = False
        user.status = spec.get("status", "active")
        user.last_login_at = (
            None if user.status == "disabled" else now - timedelta(days=index * 3)
        )
        _backdate_audits(session, before_id, created_at)
        users[spec["key"]] = user
    session.flush()
    return users


def _password_hash(password: str) -> str:
    # Keep the expensive Argon2 import and hashing in the seed path only.
    from app.services.human_auth import hash_password

    return hash_password(password)


def _condition(field: str, operator: str, value: str) -> ConditionCreate:
    return ConditionCreate(field=field, operator=operator, value=value)


def _group(
    *conditions: ConditionCreate,
    logical: str = "and",
    children: list[ConditionGroupCreate] | None = None,
) -> ConditionGroupCreate:
    return ConditionGroupCreate(
        logical_operator=logical,
        conditions=list(conditions),
        child_groups=children or [],
    )


def _create_policies(
    session: Session,
    fields: dict[str, AssignmentFieldDefinition],
    roles: dict[str, Role],
    now: datetime,
) -> dict[str, Policy]:
    today = now.date()
    policies: dict[str, Policy] = {}

    def add_policy(
        name: str,
        status: str,
        versions: list[dict[str, Any]],
        created_by: str = "priya.raman@cedarharbor.example",
    ) -> Policy:
        policy = Policy(
            name=name,
            status=status,
            created_by=created_by,
            created_at=now - timedelta(days=720 - len(policies) * 23),
        )
        session.add(policy)
        session.flush()
        record_audit_log(
            session,
            actor=created_by,
            entity_type="Policy",
            entity_id=policy.id,
            action="created",
            before=None,
            after=snapshot_entity(policy),
            timestamp=policy.created_at.replace(tzinfo=UTC)
            if policy.created_at.tzinfo is None
            else policy.created_at,
        )
        for version_index, version in enumerate(versions):
            before_id = _max_audit_id(session)
            values = [
                PolicyValueCreate(
                    assignment_field_definition_id=fields[field_name].id, value=value
                )
                for field_name, value in version["values"]
            ]
            created_at = version.pop(
                "created_at", now - timedelta(days=700 - version_index * 100)
            )
            record = create_policy_version_from_input(
                session,
                policy,
                PolicyVersionCreate(
                    priority=version["priority"],
                    effective_from=version["effective_from"],
                    effective_until=version.get("effective_until"),
                    created_by=created_by,
                    condition_group=version["conditions"],
                    values=values,
                ),
                created_by,
            )
            record.created_at = created_at.replace(tzinfo=None)
            _backdate_audits(session, before_id, created_at)
        policies[name] = policy
        return policy

    full_time = _group(_condition("employee_type", "=", "Full-time"))
    add_policy(
        "Core Full-time Employee Package",
        "active",
        [
            {
                "priority": 10,
                "effective_from": today - timedelta(days=900),
                "effective_until": today - timedelta(days=121),
                "created_at": now - timedelta(days=900),
                "conditions": full_time,
                "values": [
                    ("Benefits Plan", "Harbor Health PPO"),
                    ("Laptop Profile", "Managed Standard Laptop"),
                    ("Application Access", "Slack"),
                    ("Application Access", "Google Workspace"),
                    ("Compliance Training", "Annual Security Awareness"),
                    ("Travel Approval Limit", "USD 2,500"),
                    ("Data Classification", "Internal"),
                ],
            },
            {
                "priority": 10,
                "effective_from": today - timedelta(days=120),
                "created_at": now - timedelta(days=145),
                "conditions": full_time,
                "values": [
                    ("Benefits Plan", "Harbor Health PPO 2026"),
                    ("Laptop Profile", "Managed Standard Laptop"),
                    ("Application Access", "Slack"),
                    ("Application Access", "Google Workspace"),
                    ("Application Access", "1Password"),
                    ("Compliance Training", "Annual Security Awareness"),
                    ("Travel Approval Limit", "USD 2,500"),
                    ("Data Classification", "Internal"),
                ],
            },
        ],
    )
    add_policy(
        "Illinois Payroll and Compliance",
        "active",
        [
            {
                "priority": 30,
                "effective_from": today - timedelta(days=800),
                "conditions": _group(_condition("state", "=", "Illinois")),
                "values": [
                    ("Pay Schedule", "Semi-monthly"),
                    ("Compliance Training", "Illinois Workplace Conduct"),
                ],
            }
        ],
    )
    add_policy(
        "Standard US Payroll",
        "active",
        [
            {
                "priority": 10,
                "effective_from": today - timedelta(days=800),
                "conditions": _group(_condition("employee_type", "=", "Full-time")),
                "values": [("Pay Schedule", "Biweekly")],
            }
        ],
    )
    add_policy(
        "Contingent Worker Baseline",
        "active",
        [
            {
                "priority": 40,
                "effective_from": today - timedelta(days=700),
                "conditions": _group(_condition("employee_type", "=", "Contractor")),
                "values": [
                    ("Pay Schedule", "Monthly invoice"),
                    ("Benefits Plan", "Not eligible - contractor"),
                    ("Laptop Profile", "BYOD - managed browser"),
                    ("Application Access", "Google Workspace Guest"),
                    ("Compliance Training", "Contractor Security Briefing"),
                    ("Data Classification", "Restricted - need to know"),
                ],
            }
        ],
    )
    add_policy(
        "Engineering Workspace Access",
        "active",
        [
            {
                "priority": 35,
                "effective_from": today - timedelta(days=760),
                "conditions": _group(_condition("department", "=", "Engineering")),
                "values": [
                    ("Laptop Profile", "Engineering Workstation"),
                    ("Application Access", "GitHub Enterprise"),
                    ("Application Access", "Linear"),
                    ("Application Access", "Sentry"),
                    ("Application Access", "AWS Sandbox"),
                    ("Data Classification", "Confidential Engineering"),
                ],
            }
        ],
    )
    add_policy(
        "Field Operations Readiness",
        "active",
        [
            {
                "priority": 35,
                "effective_from": today - timedelta(days=730),
                "conditions": _group(_condition("department", "=", "Field Operations")),
                "values": [
                    ("Laptop Profile", "Rugged Field Tablet"),
                    ("Application Access", "ServiceMax"),
                    ("Application Access", "DroneDeploy"),
                    ("Facility Access", "All Wind Sites"),
                    ("Compliance Training", "OSHA 10"),
                    ("Safety Equipment", "Class E Hard Hat"),
                    ("Safety Equipment", "Arc-rated Field Kit"),
                    ("Travel Approval Limit", "USD 7,500"),
                    ("Data Classification", "Operational Confidential"),
                ],
            }
        ],
    )
    add_policy(
        "Customer Team Toolkit",
        "active",
        [
            {
                "priority": 25,
                "effective_from": today - timedelta(days=690),
                "conditions": _group(
                    _condition("department", "=", "Sales"),
                    logical="or",
                    children=[
                        _group(_condition("department", "=", "Customer Success"))
                    ],
                ),
                "values": [
                    ("Laptop Profile", "Travel Lightweight Laptop"),
                    ("Application Access", "HubSpot"),
                    ("Application Access", "Gong"),
                    ("Data Classification", "Customer Confidential"),
                ],
            }
        ],
    )
    add_policy(
        "People Manager Responsibilities",
        "active",
        [
            {
                "priority": 45,
                "effective_from": today - timedelta(days=680),
                "effective_until": today + timedelta(days=59),
                "conditions": _group(_condition("is_manager", "=", "true")),
                "values": [
                    ("Application Access", "Workday Manager"),
                    ("Compliance Training", "Manager Conduct and Coaching"),
                    ("Travel Approval Limit", "USD 10,000"),
                ],
            },
            {
                "priority": 45,
                "effective_from": today + timedelta(days=60),
                "created_at": now - timedelta(days=14),
                "conditions": _group(_condition("is_manager", "=", "true")),
                "values": [
                    ("Application Access", "Workday Manager"),
                    ("Compliance Training", "Manager Conduct and Coaching"),
                    ("Travel Approval Limit", "USD 12,500"),
                ],
            },
        ],
        created_by="elena.torres@cedarharbor.example",
    )
    add_policy(
        "Executive Stewardship",
        "active",
        [
            {
                "priority": 70,
                "effective_from": today - timedelta(days=800),
                "conditions": _group(_condition("management_level", "=", "0")),
                "values": [
                    ("Application Access", "Board Portal"),
                    ("Travel Approval Limit", "USD 25,000"),
                    ("Data Classification", "Board Confidential"),
                ],
            }
        ],
        created_by="nadia.okafor@cedarharbor.example",
    )
    add_policy(
        "Three-Year Service Benefits",
        "active",
        [
            {
                "priority": 25,
                "effective_from": today - timedelta(days=600),
                "conditions": _group(_condition("tenure", ">=", "3 years")),
                "values": [
                    ("Benefits Plan", "Harbor Health PPO 2026 + Service HSA"),
                    ("Compliance Training", "Experienced Employee Refresher"),
                ],
            }
        ],
        created_by="elena.torres@cedarharbor.example",
    )
    add_policy(
        "Chicago Headquarters Access",
        "active",
        [
            {
                "priority": 20,
                "effective_from": today - timedelta(days=620),
                "conditions": _group(_condition("location", "=", "Chicago HQ")),
                "values": [
                    ("Facility Access", "Chicago HQ - General"),
                    ("Application Access", "Envoy Visitors"),
                ],
            }
        ],
    )
    add_policy(
        "Incident Response Duty",
        "active",
        [
            {
                "priority": 60,
                "effective_from": today - timedelta(days=500),
                "conditions": _group(
                    _condition("location", "=", "Network Operations Room")
                ),
                "values": [
                    ("Application Access", "PagerDuty"),
                    ("Application Access", "Statuspage"),
                    ("On-call Rotation", "Wind Platform Primary"),
                    ("Facility Access", "Network Operations Room"),
                ],
            }
        ],
    )
    add_policy(
        "Blade Inspection Certification",
        "active",
        [
            {
                "priority": 50,
                "effective_from": today - timedelta(days=470),
                "conditions": _group(
                    _condition("location", "=", "Blade Training Center")
                ),
                "values": [
                    ("Application Access", "Inspection Evidence Vault"),
                    ("Compliance Training", "Annual Rope Rescue Recertification"),
                    ("Safety Equipment", "Fall Arrest Harness"),
                ],
            }
        ],
    )
    add_policy(
        "Responsible AI Pilot",
        "draft",
        [
            {
                "priority": 55,
                "effective_from": today + timedelta(days=30),
                "conditions": _group(
                    _condition("department", "=", "Engineering"),
                    logical="or",
                    children=[_group(_condition("department", "=", "Product"))],
                ),
                "values": [
                    ("Application Access", "Approved AI Coding Assistant"),
                    ("Compliance Training", "Responsible AI for Product Teams"),
                ],
            }
        ],
    )
    add_policy(
        "Legacy VPN Access",
        "archived",
        [
            {
                "priority": 15,
                "effective_from": today - timedelta(days=1000),
                "effective_until": today - timedelta(days=401),
                "conditions": _group(_condition("employee_type", "=", "Full-time")),
                "values": [("Application Access", "Legacy Pulse VPN")],
            }
        ],
        created_by="elliot.park@cedarharbor.example",
    )

    for policy in policies.values():
        sync_policy_version_schedules(session, policy, as_of=now)
    session.flush()
    return policies


def _attach_group_policies(
    session: Session, groups: dict[str, Group], policies: dict[str, Policy]
) -> None:
    links = (
        ("Incident Response", "Incident Response Duty"),
        ("Blade Inspection Certified", "Blade Inspection Certification"),
    )
    session.add_all(
        GroupPolicy(group_id=groups[group_name].id, policy_id=policies[policy_name].id)
        for group_name, policy_name in links
    )
    session.flush()


def _create_overrides(
    session: Session,
    employees: dict[str, Employee],
    fields: dict[str, AssignmentFieldDefinition],
    now: datetime,
) -> None:
    retired = EmployeeOverride(
        employee_id=employees["priya"].id,
        assignment_field_definition_id=fields["Travel Approval Limit"].id,
        value="USD 4,000",
        retired_at=now - timedelta(days=40),
    )
    active = (
        EmployeeOverride(
            employee_id=employees["priya"].id,
            assignment_field_definition_id=fields["Travel Approval Limit"].id,
            value="USD 5,000",
        ),
        EmployeeOverride(
            employee_id=employees["mia"].id,
            assignment_field_definition_id=fields["Travel Approval Limit"].id,
            value="USD 12,000",
        ),
        EmployeeOverride(
            employee_id=employees["mateo"].id,
            assignment_field_definition_id=fields["Facility Access"].id,
            value="Denver Partner Yard",
        ),
        EmployeeOverride(
            employee_id=employees["luca"].id,
            assignment_field_definition_id=fields["Laptop Profile"].id,
            value="Managed Contractor MacBook",
        ),
    )
    session.add_all((retired, *active))
    session.flush()
    record_audit_log(
        session,
        actor="elena.torres@cedarharbor.example",
        entity_type="EmployeeOverride",
        entity_id=retired.id,
        action="retired",
        before={"value": retired.value},
        after=None,
        timestamp=retired.retired_at,
    )
    for index, override in enumerate(active):
        record_audit_log(
            session,
            actor="elena.torres@cedarharbor.example"
            if index == 0
            else "marcus.li@cedarharbor.example",
            entity_type="EmployeeOverride",
            entity_id=override.id,
            action="created",
            before=None,
            after=snapshot_entity(override),
            timestamp=now - timedelta(days=35 - index * 8),
        )


def _create_auth_history(
    session: Session, users: dict[str, User], now: datetime
) -> None:
    sessions = (
        AuthSession(
            user_id=users["nadia"].id,
            token_hash=hash_session_token("expired-seed-session-nadia"),
            created_at=now - timedelta(days=18),
            expires_at=now - timedelta(days=17),
            last_seen_at=now - timedelta(days=17, minutes=20),
            revoked_at=None,
            reauthenticated_at=now - timedelta(days=18),
            created_ip="10.24.8.14",
            last_ip="10.24.8.14",
            user_agent="Mozilla/5.0 CedarHarbor-Managed-Chrome",
        ),
        AuthSession(
            user_id=users["elliot"].id,
            token_hash=hash_session_token("revoked-seed-session-elliot"),
            created_at=now - timedelta(days=9),
            expires_at=now + timedelta(days=1),
            last_seen_at=now - timedelta(days=8),
            revoked_at=now - timedelta(days=8),
            reauthenticated_at=now - timedelta(days=9),
            created_ip="10.24.8.31",
            last_ip="10.24.8.31",
            user_agent="Mozilla/5.0 CedarHarbor-Managed-Safari",
        ),
        AuthSession(
            user_id=users["priya"].id,
            token_hash=hash_session_token("expired-seed-session-priya"),
            created_at=now - timedelta(days=4),
            expires_at=now - timedelta(days=3),
            last_seen_at=now - timedelta(days=3, hours=14),
            revoked_at=None,
            reauthenticated_at=now - timedelta(days=4),
            created_ip="10.24.9.22",
            last_ip="10.24.9.22",
            user_agent="Mozilla/5.0 CedarHarbor-Managed-Chrome",
        ),
    )
    session.add_all(sessions)
    events = (
        ("nadia", "root_account_created", "critical", {"ip": "10.24.8.14"}, 640, True),
        ("elliot", "login_succeeded", "info", {"ip": "10.24.8.31"}, 9, True),
        ("elliot", "other_sessions_revoked", "warning", {"revoked_count": 2}, 8, True),
        (
            "priya",
            "login_from_new_context",
            "warning",
            {"ip": "172.18.4.55", "new_address": True, "new_device": False},
            22,
            True,
        ),
        ("priya", "login_succeeded", "info", {"ip": "10.24.9.22"}, 4, True),
        (
            "kendra",
            "account_suspended",
            "critical",
            {
                "actor": "nadia.okafor@cedarharbor.example",
                "reason": "Quarterly access review",
            },
            75,
            True,
        ),
        (
            "beau",
            "account_disabled",
            "critical",
            {
                "actor": "nadia.okafor@cedarharbor.example",
                "reason": "Vendor engagement ended",
            },
            120,
            True,
        ),
    )
    session.add_all(
        SecurityEvent(
            user_id=users[key].id,
            event_type=event_type,
            severity=severity,
            details=details,
            created_at=now - timedelta(days=days),
            acknowledged_at=(now - timedelta(days=max(days - 1, 0)))
            if acknowledged
            else None,
        )
        for key, event_type, severity, details, days, acknowledged in events
    )
    session.flush()


def _create_api_credentials(session: Session, now: datetime) -> None:
    session.add_all(
        (
            APICredential(
                name="Seed read-only reporting",
                subject="cedar-harbor-bi",
                token_prefix=READ_ONLY_API_TOKEN[:12],
                token_hash=hash_token(READ_ONLY_API_TOKEN),
                scopes=["read", "audit"],
                created_by=SEED_ROOT_EMAIL,
                created_at=now - timedelta(days=210),
                expires_at=now + timedelta(days=155),
            ),
            APICredential(
                name="Retired HRIS sync",
                subject="cedar-harbor-hris",
                token_prefix="wpa_retired_",
                token_hash=hash_token("wpa_retired_seed_token_not_for_use"),
                scopes=["read", "execute"],
                created_by=SEED_ROOT_EMAIL,
                created_at=now - timedelta(days=480),
                expires_at=None,
                revoked_at=now - timedelta(days=90),
            ),
        )
    )
    session.flush()


def _preview(
    change_type: str,
    *,
    affected_employees: int,
) -> dict[str, Any]:
    return {
        "type": change_type,
        "valid": True,
        "affected_employee_count": affected_employees,
        "changes": [],
        "conflicts": [],
        "warnings": [],
    }


def _create_approval_history(
    session: Session,
    users: dict[str, User],
    employees: dict[str, Employee],
    groups: dict[str, Group],
    fields: dict[str, AssignmentFieldDefinition],
    policies: dict[str, Policy],
    now: datetime,
) -> None:
    from app.routers.change_previews import (
        _assignment_changes,
        _current_assignments,
        _MutationContext,
    )
    from app.services.assignment_field_visibility import AssignmentFieldVisibility
    from app.services.employee_visibility import EmployeeVisibility

    digest = hashlib.sha256(b"cedar-harbor-seed-approval").hexdigest()
    pending_change = {
        "type": "group_membership_change",
        "action": "add",
        "group_id": groups["People Managers"].id,
        "employee_id": employees["imani"].id,
    }
    pending_change_model = GroupMembershipChangePreview.model_validate(pending_change)
    current_assignments = _current_assignments(
        session,
        visibility=EmployeeVisibility(unrestricted=True),
        field_visibility=AssignmentFieldVisibility(unrestricted=True),
    )
    pending_changes = _assignment_changes(
        session,
        current_assignments,
        current_assignments,
        _MutationContext(included_employee_ids={employees["imani"].id}),
    )
    pending_preview_model = ChangePreviewRead(
        type=pending_change_model.type,
        valid=True,
        affected_employee_count=0,
        changes=pending_changes,
        conflicts=[],
        warnings=[],
    )
    pending_preview = pending_preview_model.model_dump(mode="json")
    requests = (
        ChangeApprovalRequest(
            id="11111111-1111-4111-8111-111111111111",
            status="pending",
            change_type="group_membership_change",
            change=pending_change,
            preview=pending_preview,
            change_digest=change_digest(pending_change_model),
            precondition_digest=change_precondition_digest(
                session, pending_change_model, lock=False
            ),
            preview_digest=preview_digest(pending_preview_model),
            requested_by=users["priya"].email,
            requested_by_user_id=users["priya"].id,
            created_at=now - timedelta(hours=2),
            expires_at=now + timedelta(days=7),
        ),
        ChangeApprovalRequest(
            id="22222222-2222-4222-8222-222222222222",
            status="rejected",
            change_type="employee_override_change",
            change={
                "type": "employee_override_change",
                "action": "create",
                "employee_id": employees["omar"].id,
                "assignment_field_definition_id": fields["Travel Approval Limit"].id,
                "value": "USD 25,000",
                "override_id": None,
            },
            preview=_preview("employee_override_change", affected_employees=1),
            change_digest=digest,
            precondition_digest=digest,
            preview_digest=digest,
            requested_by=users["priya"].email,
            requested_by_user_id=users["priya"].id,
            created_at=now - timedelta(days=16),
            expires_at=now - timedelta(days=15),
            rejected_by=users["marcus"].email,
            rejected_at=now - timedelta(days=16, hours=-3),
        ),
        ChangeApprovalRequest(
            id="33333333-3333-4333-8333-333333333333",
            status="executed",
            change_type="policy_status_change",
            change={
                "type": "policy_status_change",
                "policy_id": policies["Legacy VPN Access"].id,
                "status": "archived",
            },
            preview=_preview("policy_status_change", affected_employees=0),
            change_digest=digest,
            precondition_digest=digest,
            preview_digest=digest,
            requested_by=users["elliot"].email,
            requested_by_user_id=users["elliot"].id,
            created_at=now - timedelta(days=401),
            expires_at=now - timedelta(days=400),
            approved_by=users["marcus"].email,
            approved_by_user_id=users["marcus"].id,
            approved_at=now - timedelta(days=400, hours=22),
            executed_at=now - timedelta(days=400, hours=21),
        ),
        ChangeApprovalRequest(
            id="44444444-4444-4444-8444-444444444444",
            status="expired",
            change_type="employee_update",
            change={
                "type": "employee_update",
                "employee_id": employees["kai"].id,
                "changes": {"department": "Product"},
            },
            preview=_preview("employee_update", affected_employees=1),
            change_digest=digest,
            precondition_digest=digest,
            preview_digest=digest,
            requested_by=users["priya"].email,
            requested_by_user_id=users["priya"].id,
            created_at=now - timedelta(days=46),
            expires_at=now - timedelta(days=45),
        ),
    )
    session.add_all(requests)
    session.add(
        ApprovedChangeExecution(
            approval_id=requests[2].id,
            change_type="policy_status_change",
            change_digest=digest,
            precondition_digest=digest,
            preview_digest=digest,
            executed_by=users["marcus"].email,
            executed_at=requests[2].executed_at,
            response={
                "policy_id": policies["Legacy VPN Access"].id,
                "status": "archived",
            },
        )
    )
    session.flush()


def _create_operational_history(
    session: Session,
    users: dict[str, User],
    employees: dict[str, Employee],
    policies: dict[str, Policy],
    now: datetime,
) -> None:
    entries = (
        (
            users["elena"].email,
            "Employee",
            employees["mateo"].id,
            "created",
            None,
            {
                "name": employees["mateo"].name,
                "department": "Field Operations",
                "location": "Remote - Denver",
            },
            80,
        ),
        (
            users["elena"].email,
            "Employee",
            employees["mia"].id,
            "changed",
            {"department": "Customer Success", "manager_id": None},
            {"department": "Sales", "manager_id": employees["sonya"].id},
            58,
        ),
        (
            users["elliot"].email,
            "Policy",
            policies["Legacy VPN Access"].id,
            "archived",
            {"status": "active"},
            {"status": "archived"},
            400,
        ),
        (
            users["priya"].email,
            "Policy",
            policies["Responsible AI Pilot"].id,
            "created_as_draft",
            None,
            {"status": "draft", "name": "Responsible AI Pilot"},
            14,
        ),
        (
            users["marcus"].email,
            "ChangeApprovalRequest",
            33333333,
            "executed",
            {"status": "approved"},
            {"status": "executed"},
            400,
        ),
        (
            "system",
            "ScheduledReconciliation",
            policies["Core Full-time Employee Package"].id,
            "processed",
            {"status": "pending"},
            {"status": "processed"},
            120,
        ),
    )
    for actor, entity_type, entity_id, action, before, after, days in entries:
        record_audit_log(
            session,
            actor=actor,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before=before,
            after=after,
            timestamp=now - timedelta(days=days),
        )


def _create_schedule_history(
    session: Session, policies: dict[str, Policy], now: datetime
) -> None:
    archived_version = policies["Legacy VPN Access"].versions[0]
    draft_version = policies["Responsible AI Pilot"].versions[0]
    session.add_all(
        (
            ScheduledReconciliation(
                entity_type="PolicyVersion",
                entity_id=archived_version.id,
                trigger_type="expires",
                scheduled_at=now - timedelta(days=400),
                status="processed",
                processed_at=now - timedelta(days=400),
            ),
            ScheduledReconciliation(
                entity_type="PolicyVersion",
                entity_id=draft_version.id,
                trigger_type="becomes_effective",
                scheduled_at=now + timedelta(days=30),
                status="cancelled",
                processed_at=None,
            ),
        )
    )


def _max_audit_id(session: Session) -> int:
    return session.scalar(select(func.coalesce(func.max(AuditLog.id), 0))) or 0


def _backdate_audits(session: Session, after_id: int, timestamp: datetime) -> None:
    for entry in session.scalars(select(AuditLog).where(AuditLog.id > after_id)):
        entry.timestamp = timestamp


def _summary(session: Session) -> SeedSummary:
    return SeedSummary(
        company=COMPANY_NAME,
        employees=session.scalar(select(func.count(Employee.id))) or 0,
        users=session.scalar(select(func.count(User.id))) or 0,
        roles=session.scalar(select(func.count(Role.id))) or 0,
        groups=session.scalar(select(func.count(Group.id))) or 0,
        policies=session.scalar(select(func.count(Policy.id))) or 0,
        assignments=session.scalar(select(func.count()).select_from(EmployeeAssignment))
        or 0,
        audit_logs=session.scalar(select(func.count(AuditLog.id))) or 0,
    )
