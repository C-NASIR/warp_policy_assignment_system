import { useId } from "react";
import type { AssignmentExplanation } from "@/lib/types";

export function OverrideDetails({ explanation }: { explanation: AssignmentExplanation }) {
  const headingId = useId();
  const replaced = explanation.selection?.replaced_policy_assignments ?? [];
  return (
    <section className="explanation-section" aria-labelledby={headingId}>
      <h4 id={headingId}>Override effect</h4>
      {replaced.length ? (
        <ul className="replacement-list">
          {replaced.map((item, index) => (
            <li key={`${item.source_policy_version_id ?? index}-${item.value ?? "value"}`}>
              <span>{item.value ?? "Unavailable value"}</span>
              <span>
                {item.policy_name
                  ? `Previously supplied by ${item.policy_name}`
                  : "Previously supplied by a policy"}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="section-help">
          No policy-derived value existed for this field. The override created the assignment.
        </p>
      )}
      {explanation.override?.id && (
        <p className="provenance">Recorded manual override #{explanation.override.id}</p>
      )}
    </section>
  );
}
