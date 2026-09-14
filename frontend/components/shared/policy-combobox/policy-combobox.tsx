"use client";

import { Search, X } from "lucide-react";
import { KeyboardEvent, useEffect, useId, useMemo, useState } from "react";
import type { Policy } from "@/lib/types";

const noExcludedPolicyIds: number[] = [];

function policyLabel(policy: Policy) {
  return `${policy.name} · Priority ${policy.versions.at(-1)?.priority ?? "—"}`;
}

export function PolicyCombobox({
  excludedPolicyIds = noExcludedPolicyIds,
  onChange,
}: {
  excludedPolicyIds?: number[];
  onChange(policy: Policy | null): void;
}) {
  const listboxId = useId();
  const excludedIds = useMemo(() => new Set(excludedPolicyIds), [excludedPolicyIds]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Policy | null>(null);
  const [results, setResults] = useState<Policy[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          limit: "50",
          offset: "0",
          status: "active",
        });
        if (query.trim() && query !== (selected ? policyLabel(selected) : "")) {
          params.set("search", query.trim());
        }
        const response = await fetch(`/api/backend/policies?${params}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Policy search failed");
        const policies = (await response.json()) as Policy[];
        setResults(policies.filter((policy) => !excludedIds.has(policy.id)));
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

  function choose(policy: Policy | null) {
    setSelected(policy);
    setQuery(policy ? policyLabel(policy) : "");
    onChange(policy);
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
          placeholder="Search active policies by name"
        />
        {(query || selected) && (
          <button
            className="manager-combobox-clear"
            type="button"
            onClick={() => choose(null)}
            aria-label="Clear policy"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {open && (
        <div className="manager-combobox-results" id={listboxId} role="listbox">
          {results.map((policy, index) => (
            <button
              className={`manager-combobox-option${index === activeIndex ? " active" : ""}`}
              id={`${listboxId}-${index}`}
              key={policy.id}
              type="button"
              role="option"
              aria-selected={policy.id === selected?.id}
              onMouseDown={(event) => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choose(policy)}
            >
              {policyLabel(policy)}
            </button>
          ))}
          {loading && <div className="manager-combobox-status">Searching…</div>}
          {!loading && failed && (
            <div className="manager-combobox-status">Policy search is unavailable.</div>
          )}
          {!loading && !failed && results.length === 0 && (
            <div className="manager-combobox-status">No matching active policies.</div>
          )}
        </div>
      )}
    </div>
  );
}
