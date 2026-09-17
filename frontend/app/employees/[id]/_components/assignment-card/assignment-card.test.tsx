import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CurrentAssignment } from "@/lib/types";
import { AssignmentCard } from "./assignment-card";

const directOrigin = {
  type: "condition_match",
  matched_clauses: [
    {
      clause_id: 12,
      conditions: [
        {
          field: "state",
          operator: "=",
          expected: "IL",
          actual: "IL",
          expected_label: "Illinois",
          actual_label: "Illinois",
          result: true,
        },
      ],
    },
  ],
};

function policyAssignment(overrides: Partial<CurrentAssignment> = {}): CurrentAssignment {
  return {
    id: 1,
    value: "Biweekly",
    source_policy_version_id: 101,
    source_override_id: null,
    assignment_field_definition: { id: 8, name: "Payroll schedule" },
    explanation: {
      reason: "policy",
      evaluation_date: "2026-09-16",
      policy: { id: 20, name: "Illinois Payroll and Compliance" },
      policy_version: { id: 101, version_number: 3 },
      origins: [directOrigin],
      selection: {
        field: "Payroll schedule",
        cardinality: "one",
        strategy: "priority",
        priority: 30,
        candidates: [
          {
            policy_id: 20,
            policy_name: "Illinois Payroll and Compliance",
            policy_version_id: 101,
            version_number: 3,
            value: "Biweekly",
            priority: 30,
            selected: true,
            outcome: "selected",
            origins: [directOrigin],
          },
          {
            policy_id: 21,
            policy_name: "Standard US Payroll",
            policy_version_id: 102,
            version_number: 1,
            value: "Monthly",
            priority: 10,
            selected: false,
            outcome: "lower_priority",
            origins: [directOrigin],
          },
        ],
        replaced_policy_assignments: [],
      },
      override: null,
    },
    ...overrides,
  };
}

function expand(assignment: CurrentAssignment, options?: { policies?: boolean; groups?: boolean }) {
  render(
    <AssignmentCard
      assignment={assignment}
      canViewPolicies={options?.policies}
      canViewGroups={options?.groups}
    />,
  );
  const button = screen.getByRole("button", {
    name: `Explain ${assignment.assignment_field_definition.name}: ${assignment.value}`,
  });
  fireEvent.click(button);
  return button;
}

describe("assignment explanation", () => {
  it("shows the selected and lower-priority candidates with readable reasons", () => {
    expand(policyAssignment(), { policies: true });
    expect(
      screen.getByText(
        /won over Standard US Payroll because priority 30 is higher than priority 10/i,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Selected — priority 30")).toBeInTheDocument();
    expect(screen.getByText("Not selected — priority 10 is lower than 30")).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: "Illinois Payroll and Compliance" })[0],
    ).toHaveAttribute("href", "/policies/20");
  });

  it("explains many-value duplicate source selection without implying global suppression", () => {
    const assignment = policyAssignment({
      value: "Slack",
      assignment_field_definition: { id: 9, name: "Application access" },
      explanation: {
        reason: "policy",
        policy: { id: 31, name: "Engineering Workspace Access" },
        origins: [directOrigin],
        selection: {
          cardinality: "many",
          strategy: "set_union",
          source_selection: "highest_priority_then_lowest_version_id",
          priority: 40,
          candidates: [
            {
              policy_name: "Engineering Workspace Access",
              value: "Slack",
              priority: 40,
              selected: true,
              outcome: "selected",
            },
            {
              policy_name: "Company Workspace Access",
              value: "Slack",
              priority: 10,
              selected: false,
              outcome: "duplicate_value",
            },
          ],
          replaced_policy_assignments: [],
        },
      },
    });
    expand(assignment);
    expect(screen.getByText(/Unique values combine/)).toBeInTheDocument();
    expect(
      screen.getByText("Same value — deduplicated; the higher-priority source was retained"),
    ).toBeInTheDocument();
    expect(screen.getByText(/2 policies supplied Slack/)).toBeInTheDocument();
  });

  it("renders direct condition evidence with labels", () => {
    expand(policyAssignment());
    expect(screen.getByText("Direct match")).toBeInTheDocument();
    expect(screen.getByText("State is Illinois")).toBeInTheDocument();
    expect(screen.getAllByText("Matched · Illinois").length).toBeGreaterThan(0);
  });

  it("renders every group origin and authorized group links", () => {
    const assignment = policyAssignment();
    assignment.explanation.origins = [
      { type: "group", group_id: 4, group_name: "Incident Response Team", matched_clauses: [] },
      { type: "group", group_id: 5, group_name: "Chicago Employees", matched_clauses: [] },
    ];
    expand(assignment, { groups: true });
    expect(screen.getByRole("link", { name: "Incident Response Team" })).toHaveAttribute(
      "href",
      "/groups/4",
    );
    expect(screen.getByRole("link", { name: "Chicago Employees" })).toHaveAttribute(
      "href",
      "/groups/5",
    );
  });

  it("shows both direct and group routes without duplicating condition evidence", () => {
    const assignment = policyAssignment();
    assignment.explanation.origins = [
      directOrigin,
      { ...directOrigin },
      { type: "group", group_id: 4, group_name: "Incident Response Team", matched_clauses: [] },
    ];
    expand(assignment);
    expect(screen.getByText("Direct match")).toBeInTheDocument();
    expect(screen.getByText("Incident Response Team")).toBeInTheDocument();
    expect(screen.getAllByText("State is Illinois")).toHaveLength(1);
  });

  it("lists every policy value replaced by an override", () => {
    const assignment = policyAssignment({
      value: "USD 3,000",
      source_policy_version_id: null,
      source_override_id: 44,
      assignment_field_definition: { id: 10, name: "Travel allowance" },
      explanation: {
        reason: "manual_override",
        evaluation_date: "2026-09-16",
        override: { id: 44, value: "USD 3,000" },
        selection: {
          cardinality: "many",
          strategy: "override_replaces_policy",
          replaced_policy_assignments: [
            { value: "USD 2,500", policy_name: "Core Full-time Employee Package" },
            { value: "USD 500", policy_name: "Field Travel Supplement" },
          ],
        },
      },
    });
    expand(assignment);
    expect(
      screen.getByText(
        /replaced USD 2,500 from Core Full-time Employee Package and USD 500 from Field Travel Supplement/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Recorded manual override #44")).toBeInTheDocument();
  });

  it("states when an override created a previously unassigned value", () => {
    const assignment = policyAssignment({
      value: "Special equipment",
      source_policy_version_id: null,
      source_override_id: 45,
      explanation: {
        reason: "manual_override",
        override: { id: 45, value: "Special equipment" },
        selection: { replaced_policy_assignments: [] },
      },
    });
    expand(assignment);
    expect(screen.getByText(/No policy value existed to replace/)).toBeInTheDocument();
    expect(screen.getByText(/override created the assignment/i)).toBeInTheDocument();
  });

  it("keeps a sparse legacy explanation readable", () => {
    const assignment = policyAssignment({
      explanation: {
        reason: "policy",
        policy: { name: "Legacy Payroll" },
        origins: [{ type: "persisted_policy_link" }],
        selection: { priority: 7, replaced_policy_assignments: [] },
      },
    });
    expand(assignment);
    expect(screen.getByText(/Legacy Payroll assigned Biweekly/)).toBeInTheDocument();
    expect(screen.getByText(/predates detailed match evidence/)).toBeInTheDocument();
  });

  it("exposes accurate expansion state and readable outcome text", () => {
    const assignment = policyAssignment();
    render(<AssignmentCard assignment={assignment} />);
    const button = screen.getByRole("button", { name: "Explain Payroll schedule: Biweekly" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(button).toHaveAccessibleName("Hide Payroll schedule: Biweekly");
    const candidateSection = screen.getByRole("heading", {
      name: "Candidate decision",
    }).parentElement;
    expect(candidateSection).not.toBeNull();
    expect(within(candidateSection!).getByText("Lower priority")).toBeInTheDocument();
  });
});
