"use client";

import { Search, X } from "lucide-react";
import { KeyboardEvent, useEffect, useId, useMemo, useState } from "react";
import { formatEmployeeId } from "@/lib/format";
import type { Employee } from "@/lib/types";

const noExcludedEmployeeIds: number[] = [];

function employeeLabel(employee: Employee) {
  return `${employee.name} · ${employee.department} · ${formatEmployeeId(employee.id)}`;
}

export function EmployeeCombobox({
  initialEmployee,
  excludedEmployeeIds = noExcludedEmployeeIds,
  invalid = false,
  required = false,
  errorMessageId,
  onChange,
}: {
  initialEmployee?: Employee;
  excludedEmployeeIds?: number[];
  invalid?: boolean;
  required?: boolean;
  errorMessageId?: string;
  onChange(employee: Employee | null): void;
}) {
  const listboxId = useId();
  const excludedIds = useMemo(() => new Set(excludedEmployeeIds), [excludedEmployeeIds]);
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
        const params = new URLSearchParams({ limit: "50", offset: "0" });
        if (query.trim() && query !== (selected ? employeeLabel(selected) : "")) {
          params.set("search", query.trim());
        }
        const response = await fetch(`/api/backend/employees?${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Employee search failed");
        const employees = (await response.json()) as Employee[];
        setResults(employees.filter((employee) => !excludedIds.has(employee.id)));
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
  }, [excludedIds, open, query, selected]);

  function choose(employee: Employee | null) {
    setSelected(employee);
    setQuery(employee ? employeeLabel(employee) : "");
    onChange(employee);
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
          aria-errormessage={invalid ? errorMessageId : undefined}
          autoComplete="off"
          required={required}
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
            onChange(null);
            setOpen(true);
            setLoading(true);
            setFailed(false);
          }}
          onKeyDown={onKeyDown}
          placeholder="Search by name, department, or Employee ID"
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
