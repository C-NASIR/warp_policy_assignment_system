"use client";

import { ChevronDown, ChevronUp, ShieldCheck, Sparkles } from "lucide-react";
import { useId, useState } from "react";
import { Badge } from "@/components/ui";
import type { CurrentAssignment } from "@/lib/types";
import { AssignmentExplanation } from "./assignment-explanation";
import { groupOrigins } from "./explanation-format";

export function AssignmentCard({
  assignment,
  canViewPolicies = false,
  canViewGroups = false,
}: {
  assignment: CurrentAssignment;
  canViewPolicies?: boolean;
  canViewGroups?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const detailsId = useId();
  const explanation = assignment.explanation;
  const isOverride =
    assignment.source_override_id !== null || explanation.reason === "manual_override";
  const policyName = explanation.policy?.name ?? (isOverride ? "Manual override" : "Policy rule");
  const groups = groupOrigins(explanation.origins);
  const sourceSummary = groups.length
    ? `Through ${groups.length === 1 ? groups[0].group_name || "an employee group" : `${groups.length} groups`}`
    : isOverride
      ? (explanation.selection?.replaced_policy_assignments?.length ?? 0) > 0
        ? "Replaces policy result"
        : "Creates this assignment"
      : explanation.selection?.priority == null
        ? "Recorded policy source"
        : `Priority ${explanation.selection.priority}`;

  return (
    <article className="assignment-card">
      <button
        className="assignment-summary"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={detailsId}
        aria-label={`${open ? "Hide" : "Explain"} ${assignment.assignment_field_definition.name}: ${assignment.value}`}
      >
        <span>
          <span className="assignment-field">{assignment.assignment_field_definition.name}</span>
          <span className="assignment-value">{assignment.value}</span>
        </span>
        <span className="assignment-source">
          <strong>{policyName}</strong>
          {sourceSummary}
        </span>
        <Badge tone={isOverride ? "warning" : "accent"}>
          {isOverride ? <ShieldCheck size={11} /> : <Sparkles size={11} />}
          {isOverride ? "Override" : "Policy"}
        </Badge>
        {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {open && (
        <div className="assignment-details" id={detailsId}>
          <AssignmentExplanation
            assignment={assignment}
            canViewPolicies={canViewPolicies}
            canViewGroups={canViewGroups}
          />
        </div>
      )}
    </article>
  );
}
