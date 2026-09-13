"use client";

import { Search, X } from "lucide-react";
import { KeyboardEvent, useEffect, useId, useState } from "react";
import type { EmployeeManagerCandidate } from "@/lib/types";

export function ManagerCombobox({
  employeeId,
  initialCandidate,
  onChange,
}: {
  employeeId?: number;
  initialCandidate?: EmployeeManagerCandidate;
  onChange(id: number | null): void;
}) {
  const listboxId = useId();
  const [query, setQuery] = useState(initialCandidate?.label ?? "");
  const [selected, setSelected] = useState<EmployeeManagerCandidate | null>(
    initialCandidate ?? null,
  );
  const [results, setResults] = useState<EmployeeManagerCandidate[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({ limit: "20" });
        if (query.trim() && query !== selected?.label) params.set("search", query.trim());
        if (employeeId) params.set("employee_id", String(employeeId));
        const response = await fetch(`/api/backend/employees/manager-candidates?${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Manager search failed");
        const candidates = (await response.json()) as EmployeeManagerCandidate[];
        setResults(candidates);
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
  }, [employeeId, open, query, selected?.label]);

  function choose(candidate: EmployeeManagerCandidate | null) {
    setSelected(candidate);
    setQuery(candidate?.label ?? "");
    onChange(candidate?.id ?? null);
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
          id="manager"
          className="input"
          role="combobox"
          aria-autocomplete="list"
          aria-controls={listboxId}
          aria-expanded={open}
          aria-activedescendant={activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined}
          autoComplete="off"
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
            aria-label="Clear manager"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {open && (
        <div className="manager-combobox-results" id={listboxId} role="listbox">
          <button
            className="manager-combobox-option"
            type="button"
            role="option"
            aria-selected={selected === null && query === ""}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => choose(null)}
          >
            No manager
          </button>
          {results.map((candidate, index) => (
            <button
              className={`manager-combobox-option${index === activeIndex ? " active" : ""}`}
              id={`${listboxId}-${index}`}
              key={candidate.id}
              type="button"
              role="option"
              aria-selected={candidate.id === selected?.id}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choose(candidate)}
            >
              {candidate.label}
            </button>
          ))}
          {loading && <div className="manager-combobox-status">Searching…</div>}
          {!loading && failed && (
            <div className="manager-combobox-status">Manager search is unavailable.</div>
          )}
          {!loading && !failed && results.length === 0 && query && (
            <div className="manager-combobox-status">No matching employees.</div>
          )}
        </div>
      )}
    </div>
  );
}
