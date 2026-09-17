import Link from "next/link";
import { useId } from "react";
import { Badge } from "@/components/ui";
import type { AssignmentCandidate } from "@/lib/types";
import {
  candidateOutcomeLabel,
  candidateReason,
  groupOrigins,
  originText,
  uniqueEvidenceClauses,
} from "./explanation-format";

function CandidateName({
  candidate,
  canViewPolicies,
}: {
  candidate: AssignmentCandidate;
  canViewPolicies: boolean;
}) {
  const name = candidate.policy_name || "Unnamed policy";
  if (canViewPolicies && candidate.policy_id) {
    return <Link href={`/policies/${candidate.policy_id}`}>{name}</Link>;
  }
  return <>{name}</>;
}

function CandidateOrigin({
  candidate,
  canViewGroups,
}: {
  candidate: AssignmentCandidate;
  canViewGroups: boolean;
}) {
  const groups = groupOrigins(candidate.origins);
  const direct = uniqueEvidenceClauses(candidate.origins).length > 0;
  if (!groups.length) return <>{originText(candidate.origins)}</>;
  return (
    <>
      {direct && "Direct condition match; "}
      Through{" "}
      {groups.map((origin, index) => (
        <span key={`${origin.group_id ?? "legacy"}-${origin.group_name ?? index}`}>
          {index > 0 && (index === groups.length - 1 ? " and " : ", ")}
          {canViewGroups && origin.group_id ? (
            <Link href={`/groups/${origin.group_id}`}>
              {origin.group_name || `Group #${origin.group_id}`}
            </Link>
          ) : (
            origin.group_name || "an employee group"
          )}
        </span>
      ))}
    </>
  );
}

export function CandidateDecisions({
  candidates,
  winnerPriority,
  cardinality,
  canViewPolicies,
  canViewGroups,
}: {
  candidates: AssignmentCandidate[] | undefined;
  winnerPriority: number | null | undefined;
  cardinality: string | null | undefined;
  canViewPolicies: boolean;
  canViewGroups: boolean;
}) {
  const headingId = useId();
  if (!candidates?.length) return null;
  return (
    <section className="explanation-section" aria-labelledby={headingId}>
      <h4 id={headingId}>Candidate decision</h4>
      {cardinality === "many" && (
        <p className="section-help">
          Unique values combine. Priority only chooses the recorded source when policies supply the
          same value.
        </p>
      )}
      <ol className="candidate-list">
        {candidates.map((candidate, index) => {
          const selected = candidate.selected || candidate.outcome === "selected";
          return (
            <li
              className={selected ? "candidate candidate-selected" : "candidate"}
              key={`${candidate.policy_version_id ?? index}-${candidate.value ?? "value"}`}
            >
              <div className="candidate-heading">
                <strong>
                  <CandidateName candidate={candidate} canViewPolicies={canViewPolicies} />
                </strong>
                <Badge
                  tone={
                    selected
                      ? "success"
                      : candidate.outcome === "duplicate_value"
                        ? "accent"
                        : "neutral"
                  }
                >
                  {candidateOutcomeLabel(candidate)}
                </Badge>
              </div>
              <dl className="candidate-facts">
                <div>
                  <dt>Value</dt>
                  <dd>{candidate.value ?? "Unavailable"}</dd>
                </div>
                <div>
                  <dt>Priority</dt>
                  <dd>{candidate.priority ?? "Unavailable"}</dd>
                </div>
                <div>
                  <dt>Version</dt>
                  <dd>
                    {candidate.version_number == null
                      ? "Unavailable"
                      : `v${candidate.version_number}`}
                  </dd>
                </div>
                <div>
                  <dt>Origin</dt>
                  <dd>
                    <CandidateOrigin candidate={candidate} canViewGroups={canViewGroups} />
                  </dd>
                </div>
              </dl>
              <p className="candidate-reason">{candidateReason(candidate, winnerPriority)}</p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
