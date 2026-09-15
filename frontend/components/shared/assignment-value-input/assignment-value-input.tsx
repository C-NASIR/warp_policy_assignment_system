"use client";

import type { AssignmentFieldOption } from "@/lib/types";

export function AssignmentValueInput({
  field,
  value,
  invalid = false,
  label = "assignment value",
  onChange,
}: {
  field: AssignmentFieldOption | undefined;
  value: string;
  invalid?: boolean;
  label?: string;
  onChange(value: string): void;
}) {
  if (field?.input.type === "select") {
    return (
      <select
        className={`select${invalid ? " field-invalid" : ""}`}
        required
        aria-invalid={invalid}
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Choose value</option>
        {field.input.options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  return (
    <input
      className={`input${invalid ? " field-invalid" : ""}`}
      required
      aria-invalid={invalid}
      aria-label={label}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder="Enter assignment value"
    />
  );
}
