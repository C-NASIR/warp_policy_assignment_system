import { Check, Network } from "lucide-react";
import Link from "next/link";
import { useId } from "react";
import { Badge } from "@/components/ui";
import type { AssignmentOrigin } from "@/lib/types";
import {
  actualConditionValue,
  conditionLabel,
  groupOrigins,
  uniqueEvidenceClauses,
} from "./explanation-format";

export function ConditionEvidence({
  origins,
  canViewGroups,
}: {
  origins: AssignmentOrigin[] | undefined;
  canViewGroups: boolean;
}) {
  const headingId = useId();
  const clauses = uniqueEvidenceClauses(origins);
  const groups = groupOrigins(origins);
  const persisted = (origins ?? []).some((origin) => origin.type === "persisted_policy_link");
  if (!clauses.length && !groups.length && !persisted) return null;

  return (
    <section className="explanation-section" aria-labelledby={headingId}>
      <h4 id={headingId}>Why it applied</h4>
      {clauses.length > 0 && (
        <div className="origin-block">
          <div className="origin-label">
            <Check size={13} aria-hidden="true" /> Direct match
          </div>
          {clauses.length > 1 && (
            <p className="origin-help">Any one of these condition groups was enough to match.</p>
          )}
          {clauses.some((clause) => clause.conditions.length > 1) && (
            <p className="origin-help">Every condition within a match path matched.</p>
          )}
          <ol className="clause-list">
            {clauses.map((clause, clauseIndex) => (
              <li key={clause.key}>
                {clauses.length > 1 && (
                  <span className="clause-title">Match path {clauseIndex + 1}</span>
                )}
                <ul className="evidence-list">
                  {clause.conditions.map((condition, conditionIndex) => (
                    <li className="evidence-row" key={`${clause.key}-${conditionIndex}`}>
                      <span>{conditionLabel(condition)}</span>
                      <Badge tone="success">Matched · {actualConditionValue(condition)}</Badge>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      )}
      {groups.length > 0 && (
        <div className="origin-block">
          <div className="origin-label">
            <Network size={13} aria-hidden="true" /> Group membership
          </div>
          <ul className="group-origin-list">
            {groups.map((origin, index) => (
              <li key={`${origin.group_id ?? "legacy"}-${origin.group_name ?? index}`}>
                {canViewGroups && origin.group_id ? (
                  <Link href={`/groups/${origin.group_id}`}>
                    {origin.group_name || `Group #${origin.group_id}`}
                  </Link>
                ) : (
                  <span>{origin.group_name || "Employee group"}</span>
                )}
                <span>contributed this policy</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {persisted && !clauses.length && !groups.length && (
        <p className="origin-help">
          This historical snapshot records the policy link, but predates detailed match evidence.
        </p>
      )}
    </section>
  );
}
