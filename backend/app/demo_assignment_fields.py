from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoAssignmentFieldSpec:
    name: str
    cardinality: str
    options: tuple[str, ...]

    @property
    def input(self) -> dict:
        return {
            "type": "select",
            "options": [{"value": option, "label": option} for option in self.options],
        }


DEMO_ASSIGNMENT_FIELD_SPECS = (
    DemoAssignmentFieldSpec(
        "Pay Schedule",
        "one",
        ("Weekly", "Biweekly", "Semi-monthly", "Monthly", "Monthly invoice"),
    ),
    DemoAssignmentFieldSpec(
        "Benefits Plan",
        "one",
        (
            "Harbor Health PPO",
            "Harbor Health PPO 2026",
            "Harbor Health PPO 2026 + Service HSA",
            "Not eligible - contractor",
        ),
    ),
    DemoAssignmentFieldSpec(
        "Device Profile",
        "one",
        (
            "BYOD - managed browser",
            "Engineering Workstation",
            "Managed Contractor MacBook",
            "Managed Standard Laptop",
            "Rugged Field Tablet",
            "Travel Lightweight Laptop",
        ),
    ),
    DemoAssignmentFieldSpec(
        "Application Access",
        "many",
        (
            "1Password",
            "Approved AI Coding Assistant",
            "AWS Sandbox",
            "Board Portal",
            "DroneDeploy",
            "Envoy Visitors",
            "GitHub Enterprise",
            "Gong",
            "Google Workspace",
            "Google Workspace Guest",
            "HubSpot",
            "Inspection Evidence Vault",
            "Pulse VPN",
            "Linear",
            "PagerDuty",
            "Sentry",
            "ServiceMax",
            "Slack",
            "Statuspage",
            "Workday Manager",
        ),
    ),
    DemoAssignmentFieldSpec(
        "Physical Access",
        "many",
        (
            "All Wind Sites",
            "Chicago HQ - General",
            "Denver Partner Yard",
            "Network Operations Room",
        ),
    ),
    DemoAssignmentFieldSpec(
        "Compliance Training",
        "many",
        (
            "Annual Rope Rescue Recertification",
            "Annual Security Awareness",
            "Contractor Security Briefing",
            "Experienced Employee Refresher",
            "Illinois Workplace Conduct",
            "Manager Conduct and Coaching",
            "OSHA 10",
            "Responsible AI for Product Teams",
        ),
    ),
    DemoAssignmentFieldSpec(
        "Expense Approval Limit",
        "one",
        (
            "USD 2,500",
            "USD 4,000",
            "USD 5,000",
            "USD 7,500",
            "USD 10,000",
            "USD 12,000",
            "USD 12,500",
            "USD 25,000",
        ),
    ),
    DemoAssignmentFieldSpec(
        "Information Access Level",
        "one",
        (
            "Internal",
            "Customer Confidential",
            "Operational Confidential",
            "Confidential Engineering",
            "Restricted - need to know",
            "Board Confidential",
        ),
    ),
)
