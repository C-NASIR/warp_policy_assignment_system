import { Check } from "lucide-react";
import { classNames } from "@/lib/class-names";
import styles from "./workflow-progress.module.css";

export type WorkflowStep = {
  label: string;
  description: string;
};

export function WorkflowProgress({
  steps,
  currentStep,
  compact = false,
}: {
  steps: WorkflowStep[];
  currentStep: number;
  compact?: boolean;
}) {
  return (
    <nav className={classNames(styles.workflow, compact && styles.compact)} aria-label="Progress">
      <ol>
        {steps.map((step, index) => {
          const number = index + 1;
          const complete = number < currentStep;
          const current = number === currentStep;
          return (
            <li
              className={classNames(
                styles.step,
                complete && styles.complete,
                current && styles.current,
              )}
              aria-current={current ? "step" : undefined}
              key={step.label}
            >
              <span className={styles.marker} aria-hidden="true">
                {complete ? <Check size={12} strokeWidth={2.4} /> : number}
              </span>
              <span className={styles.copy}>
                <strong>{step.label}</strong>
                <small>{step.description}</small>
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
