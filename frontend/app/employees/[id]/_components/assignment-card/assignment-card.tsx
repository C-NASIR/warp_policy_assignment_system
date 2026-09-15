"use client";

import { ChevronDown, ChevronUp, Network, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui";
import { titleCase } from "@/lib/format";
import type { CurrentAssignment } from "@/lib/types";

export function AssignmentCard({ assignment }: { assignment: CurrentAssignment }) {
  const [open, setOpen] = useState(false);
  const explanation = assignment.explanation;
  const isOverride = assignment.source_override_id !== null;
  const policyName = explanation.policy?.name ?? (isOverride ? "Manual override" : "Policy rule");
  const groupName = explanation.origins?.find((item) => item.type === "group")?.group_name;
  const replacedAssignment = explanation.selection?.replaced_policy_assignments[0];
  const evidence =
    explanation.origins
      ?.flatMap((item) => item.matched_clauses ?? [])
      .flatMap((clause) => clause.conditions ?? []) ?? [];

  return (
    <article className="assignment-card">
      <button
        className="assignment-summary"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span>
          <span className="assignment-field">{assignment.assignment_field_definition.name}</span>
          <span className="assignment-value">{assignment.value}</span>
        </span>
        <span className="assignment-source">
          <strong>{policyName}</strong>
          {groupName
            ? `Through ${groupName}`
            : isOverride
              ? "Replaces policy result"
              : `Priority ${explanation.selection?.priority ?? "—"}`}
        </span>
        <Badge tone={isOverride ? "warning" : "accent"}>
          {isOverride ? <ShieldCheck size={11} /> : <Sparkles size={11} />}
          {isOverride ? "Override" : "Policy"}
        </Badge>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <div className="assignment-details">
          <div className="explanation-box">
            <div className="explanation-lead">
              {groupName ? (
                <Network size={14} />
              ) : isOverride ? (
                <ShieldCheck size={14} />
              ) : (
                <Sparkles size={14} />
              )}
              <span>
                {isOverride
                  ? `This value was assigned manually${replacedAssignment ? ` and replaced ${replacedAssignment.value}${replacedAssignment.policy_name ? ` from ${replacedAssignment.policy_name}` : " from a policy"}.` : "."}`
                  : groupName
                    ? `${policyName} applies because this employee belongs to the ${groupName} group.`
                    : `${policyName} matched this employee and won the priority comparison.`}
              </span>
            </div>
            {evidence.length > 0 && (
              <div className="evidence-list">
                {evidence.map((item, index) => (
                  <div className="evidence-row" key={`${item.field}-${index}`}>
                    <span>
                      {titleCase(item.field ?? "Condition")} {item.operator}{" "}
                      {item.expected_label ?? String(item.expected)}
                    </span>
                    <Badge tone="success">
                      Matched · {item.actual_label ?? String(item.actual)}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
