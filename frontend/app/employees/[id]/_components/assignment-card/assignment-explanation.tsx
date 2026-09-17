import { ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import type { CurrentAssignment } from "@/lib/types";
import { CandidateDecisions } from "./candidate-decisions";
import { ConditionEvidence } from "./condition-evidence";
import { DecisionMetadata } from "./decision-metadata";
import { explanationSummary } from "./explanation-format";
import { OverrideDetails } from "./override-details";

export function AssignmentExplanation({
  assignment,
  canViewPolicies,
  canViewGroups,
}: {
  assignment: CurrentAssignment;
  canViewPolicies: boolean;
  canViewGroups: boolean;
}) {
  const explanation = assignment.explanation ?? {};
  const isOverride =
    assignment.source_override_id !== null || explanation.reason === "manual_override";
  return (
    <div className="explanation-box">
      <div className="explanation-lead">
        {isOverride ? (
          <ShieldCheck size={15} aria-hidden="true" />
        ) : (
          <Sparkles size={15} aria-hidden="true" />
        )}
        <div>
          <p>{explanationSummary(assignment)}</p>
          {!isOverride && explanation.policy?.name && (
            <p className="source-record">
              Source:{" "}
              {canViewPolicies && explanation.policy.id ? (
                <Link href={`/policies/${explanation.policy.id}`}>{explanation.policy.name}</Link>
              ) : (
                <strong>{explanation.policy.name}</strong>
              )}
            </p>
          )}
        </div>
      </div>
      {isOverride ? (
        <OverrideDetails explanation={explanation} />
      ) : (
        <>
          <ConditionEvidence origins={explanation.origins} canViewGroups={canViewGroups} />
          <CandidateDecisions
            candidates={explanation.selection?.candidates}
            winnerPriority={explanation.selection?.priority}
            cardinality={explanation.selection?.cardinality}
            canViewPolicies={canViewPolicies}
            canViewGroups={canViewGroups}
          />
        </>
      )}
      <DecisionMetadata explanation={explanation} />
    </div>
  );
}
