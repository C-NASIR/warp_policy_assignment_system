"use client";

import { Search, X } from "lucide-react";
import { KeyboardEvent, useEffect, useId, useState } from "react";
import { formatEmployeeId } from "@/lib/format";
import type { ConditionField, Employee, EmployeeReferenceData } from "@/lib/types";
import { StateCombobox } from "@/components/shared";

function employeeLabel(employee: Employee) {
  return `${employee.name} · ${employee.department} · ${formatEmployeeId(employee.id)}`;
}

function EmployeeReferenceInput({
  value,
  employees,
  invalid,
  onChange,
}: {
  value: string;
  employees: Employee[];
  invalid: boolean;
  onChange(value: string): void;
}) {
  const listboxId = useId();
  const initialEmployee = employees.find((employee) => String(employee.id) === value);
  const [query, setQuery] = useState(initialEmployee ? employeeLabel(initialEmployee) : "");
  const [selected, setSelected] = useState<Employee | null>(initialEmployee ?? null);
  const [results, setResults] = useState<Employee[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({ limit: "20", offset: "0" });
        if (query.trim() && query !== (selected ? employeeLabel(selected) : "")) {
          params.set("search", query.trim());
        }
        const response = await fetch(`/api/backend/employees?${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Employee search failed");
        setResults((await response.json()) as Employee[]);
        setActiveIndex(-1);
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setResults([]);
          setFailed(true);
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [open, query, selected]);

  function choose(employee: Employee | null) {
    setSelected(employee);
    setQuery(employee ? employeeLabel(employee) : "");
    onChange(employee ? String(employee.id) : "");
    setOpen(false);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setLoading(true);
      setFailed(false);
      setActiveIndex((current) => Math.min(current + 1, results.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, -1));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      choose(results[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div
      className="manager-combobox"
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <div className="manager-combobox-control">
        <Search size={14} aria-hidden="true" />
        <input
          className={`input${invalid ? " field-invalid" : ""}`}
          role="combobox"
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={open}
          aria-activedescendant={activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined}
          aria-invalid={invalid}
          autoComplete="off"
          required
          value={query}
          onFocus={() => {
            setOpen(true);
            setLoading(true);
            setFailed(false);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setSelected(null);
            setResults([]);
            setActiveIndex(-1);
            onChange("");
            setOpen(true);
            setLoading(true);
            setFailed(false);
          }}
          onKeyDown={onKeyDown}
          placeholder="Search by name or Employee ID"
        />
        {(query || selected) && (
          <button
            className="manager-combobox-clear"
            type="button"
            onClick={() => choose(null)}
            aria-label="Clear employee"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {open && (
        <div className="manager-combobox-results" id={listboxId} role="listbox">
          {results.map((employee, index) => (
            <button
              className={`manager-combobox-option${index === activeIndex ? " active" : ""}`}
              id={`${listboxId}-${index}`}
              key={employee.id}
              type="button"
              role="option"
              aria-selected={employee.id === selected?.id}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choose(employee)}
            >
              {employeeLabel(employee)}
            </button>
          ))}
          {loading && <div className="manager-combobox-status">Searching…</div>}
          {!loading && failed && (
            <div className="manager-combobox-status">Employee search is unavailable.</div>
          )}
          {!loading && !failed && results.length === 0 && (
            <div className="manager-combobox-status">No matching employees.</div>
          )}
        </div>
      )}
    </div>
  );
}

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
      <EmployeeReferenceInput
        value={value}
        employees={employees}
        invalid={invalid}
        onChange={onChange}
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
