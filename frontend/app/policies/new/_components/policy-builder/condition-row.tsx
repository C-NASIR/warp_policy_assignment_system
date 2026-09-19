"use client";

import { Trash2 } from "lucide-react";
import { ConditionValueInput } from "./condition-value-input";
import type { Condition, ConditionField, Employee, EmployeeReferenceData } from "@/lib/types";

export type BuilderCondition = Condition & { rowId: number };

export function authorableConditionFields(fields: ConditionField[]) {
  const authorable = fields.filter((field) => field.key !== "name");
  const employee = authorable.find((field) => field.key === "employee_id");
  return employee ? [employee, ...authorable.filter((field) => field !== employee)] : authorable;
}

export function defaultCondition(): Omit<BuilderCondition, "rowId"> {
  return {
    field: "",
    operator: "=",
    value: "",
  };
}

export function ConditionRow({
  condition,
  conditionFields,
  employees,
  referenceData,
  validationAttempted,
  removeDisabled = false,
  removeLabel,
  errorMessageId,
  onChange,
  onRemove,
}: {
  condition: BuilderCondition;
  conditionFields: ConditionField[];
  employees: Employee[];
  referenceData: EmployeeReferenceData;
  validationAttempted: boolean;
  removeDisabled?: boolean;
  removeLabel: string;
  errorMessageId?: string;
  onChange(patch: Partial<BuilderCondition>): void;
  onRemove(): void;
}) {
  const definition = conditionFields.find((field) => field.key === condition.field);
  const selectableFields = authorableConditionFields(conditionFields);
  const displayedFields =
    definition && !selectableFields.some((field) => field.key === definition.key)
      ? [definition, ...selectableFields]
      : selectableFields;
  const fieldInvalid = validationAttempted && !condition.field;
  const valueInvalid = validationAttempted && Boolean(definition) && !condition.value.trim();

  return (
    <div className="condition-row">
      <select
        className={`select${fieldInvalid ? " field-invalid" : ""}`}
        required
        aria-invalid={fieldInvalid}
        aria-errormessage={fieldInvalid ? errorMessageId : undefined}
        value={condition.field}
        onChange={(event) => {
          const next = conditionFields.find((field) => field.key === event.target.value);
          onChange({
            field: event.target.value,
            operator: next?.allowed_operators[0] ?? "=",
            value: "",
          });
        }}
      >
        <option value="" disabled>
          Select condition
        </option>
        {displayedFields.map((field) => (
          <option key={field.key} value={field.key}>
            {field.label}
          </option>
        ))}
      </select>
      <select
        className="select"
        disabled={!definition}
        value={definition ? condition.operator : ""}
        onChange={(event) => onChange({ operator: event.target.value as Condition["operator"] })}
      >
        {!definition && <option value="">—</option>}
        {definition?.allowed_operators.map((operator) => (
          <option key={operator}>{operator}</option>
        ))}
      </select>
      {definition && (
        <ConditionValueInput
          key={definition.key}
          definition={definition}
          value={condition.value}
          employees={employees}
          referenceData={referenceData}
          invalid={valueInvalid}
          errorMessageId={errorMessageId}
          onChange={(value) => onChange({ value })}
        />
      )}
      {!definition && (
        <input
          className="input"
          disabled
          aria-label="Condition value"
          placeholder="Select a condition first"
        />
      )}
      <button
        className="remove-button"
        type="button"
        disabled={removeDisabled}
        onClick={onRemove}
        aria-label={removeLabel}
      >
        <Trash2 size={13} />
      </button>
    </div>
  );
}
