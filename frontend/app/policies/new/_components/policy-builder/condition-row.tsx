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

export function defaultCondition(fields: ConditionField[]): Omit<BuilderCondition, "rowId"> {
  const definition = authorableConditionFields(fields)[0] ?? fields[0];
  return {
    field: definition?.key ?? "state",
    operator: definition?.allowed_operators[0] ?? "=",
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
  onChange(patch: Partial<BuilderCondition>): void;
  onRemove(): void;
}) {
  const definition =
    conditionFields.find((field) => field.key === condition.field) ?? conditionFields[0];
  const selectableFields = authorableConditionFields(conditionFields);
  const displayedFields =
    definition && !selectableFields.some((field) => field.key === definition.key)
      ? [definition, ...selectableFields]
      : selectableFields;
  const invalid = validationAttempted && !condition.value.trim();

  return (
    <div className="condition-row">
      <select
        className="select"
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
        {displayedFields.map((field) => (
          <option key={field.key} value={field.key}>
            {field.label}
          </option>
        ))}
      </select>
      <select
        className="select"
        value={condition.operator}
        onChange={(event) => onChange({ operator: event.target.value as Condition["operator"] })}
      >
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
          invalid={invalid}
          onChange={(value) => onChange({ value })}
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
