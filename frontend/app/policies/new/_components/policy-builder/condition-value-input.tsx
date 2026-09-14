import type { ConditionField, Employee, EmployeeReferenceData } from "@/lib/types";
import { EmployeeCombobox, StateCombobox } from "@/components/shared";

function includeCurrentValue(options: string[], value: string) {
  return value && !options.includes(value) ? [value, ...options] : options;
}

function durationYears(value: string) {
  return /^(?:P)?(\d+)(?:Y|\s+years?)?$/i.exec(value.trim())?.[1] ?? value;
}

export function ConditionValueInput({
  definition,
  value,
  employees,
  referenceData,
  invalid,
  onChange,
}: {
  definition: ConditionField;
  value: string;
  employees: Employee[];
  referenceData: EmployeeReferenceData;
  invalid: boolean;
  onChange(value: string): void;
}) {
  const input = definition.input;

  if (input.type === "resource" && input.reference_resource === "employees") {
    return (
      <EmployeeCombobox
        initialEmployee={employees.find((employee) => String(employee.id) === value)}
        invalid={invalid}
        required
        onChange={(employee) => onChange(employee ? String(employee.id) : "")}
      />
    );
  }

  if (input.type === "resource" && input.reference_resource === "states") {
    return (
      <StateCombobox
        states={referenceData.states}
        value={value}
        invalid={invalid}
        onChange={onChange}
      />
    );
  }

  const referenceOptions =
    input.reference_resource === "departments"
      ? referenceData.departments
      : input.reference_resource === "employee_types"
        ? referenceData.employee_types
        : null;
  if (referenceOptions) {
    return (
      <select
        className={`select${invalid ? " field-invalid" : ""}`}
        required
        aria-invalid={invalid}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Choose value</option>
        {includeCurrentValue(referenceOptions, value).map((option) => (
          <option value={option} key={option}>
            {option}
          </option>
        ))}
      </select>
    );
  }

  if (input.type === "select") {
    return (
      <select
        className={`select${invalid ? " field-invalid" : ""}`}
        required
        aria-invalid={invalid}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Choose value</option>
        {input.options.map((option) => (
          <option value={option.value} key={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  }

  if (input.type === "duration") {
    return (
      <div className="condition-duration-input">
        <input
          className={`input${invalid ? " field-invalid" : ""}`}
          required
          aria-invalid={invalid}
          type="number"
          min={input.minimum ?? 1}
          step={1}
          value={durationYears(value)}
          onChange={(event) => onChange(event.target.value ? `${event.target.value} years` : "")}
          placeholder={input.placeholder ?? undefined}
        />
        <span>years</span>
      </div>
    );
  }

  return (
    <input
      className={`input${invalid ? " field-invalid" : ""}`}
      required
      aria-invalid={invalid}
      type={input.type === "date" ? "date" : input.type === "number" ? "number" : "text"}
      min={input.type === "number" ? (input.minimum ?? undefined) : undefined}
      step={input.type === "number" ? 1 : undefined}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      placeholder={input.placeholder ?? "Enter value"}
    />
  );
}
