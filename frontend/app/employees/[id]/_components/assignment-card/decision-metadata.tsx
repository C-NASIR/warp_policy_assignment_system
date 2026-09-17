import { useId } from "react";
import type { AssignmentExplanation } from "@/lib/types";
import { cardinalityLabel, formatExplanationDate, strategyLabel } from "./explanation-format";

export function DecisionMetadata({ explanation }: { explanation: AssignmentExplanation }) {
  const headingId = useId();
  const selection = explanation.selection;
  const details = [
    explanation.evaluation_date
      ? ["Evaluation date", formatExplanationDate(explanation.evaluation_date)]
      : null,
    selection?.cardinality
      ? ["Assignment cardinality", cardinalityLabel(selection.cardinality)]
      : null,
    selection?.strategy ? ["Selection strategy", strategyLabel(selection.strategy)] : null,
    selection?.priority != null ? ["Winning priority", String(selection.priority)] : null,
    explanation.policy_version?.version_number != null
      ? ["Policy version", `Version ${explanation.policy_version.version_number}`]
      : null,
  ].filter((item): item is string[] => item !== null);
  if (!details.length && !selection?.source_selection) return null;

  return (
    <section className="explanation-section decision-details" aria-labelledby={headingId}>
      <h4 id={headingId}>Decision details</h4>
      {details.length > 0 && (
        <dl className="metadata-grid">
          {details.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}
      {selection?.source_selection === "highest_priority_then_lowest_version_id" && (
        <details className="technical-detail">
          <summary>How duplicate sources are chosen</summary>
          <p>
            The highest-priority policy is recorded. If priorities tie, the earliest policy version
            record is used for a deterministic result.
          </p>
        </details>
      )}
    </section>
  );
}
