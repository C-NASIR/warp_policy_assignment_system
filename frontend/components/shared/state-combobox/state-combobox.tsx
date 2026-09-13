"use client";

import { Search, X } from "lucide-react";
import { KeyboardEvent, useId, useMemo, useState } from "react";
import type { StateOption } from "@/lib/types";

const GROUPS: { key: StateOption["group"]; label: string }[] = [
  { key: "states", label: "States" },
  { key: "territories", label: "Territories" },
  { key: "other", label: "Other" },
];

export function stateOptionLabel(option: StateOption) {
  return `${option.label} · ${option.code}`;
}

export function StateCombobox({
  states,
  value,
  invalid = false,
  onChange,
}: {
  states: StateOption[];
  value: string;
  invalid?: boolean;
  onChange(value: string): void;
}) {
  const listboxId = useId();
  const selected = states.find((option) => option.code === value) ?? null;
  const [query, setQuery] = useState(selected ? stateOptionLabel(selected) : "");
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const search =
    selected && query === stateOptionLabel(selected) ? "" : query.trim().toLocaleLowerCase();
  const filtered = useMemo(
    () =>
      states.filter(
        (option) =>
          !search ||
          option.code.toLocaleLowerCase().includes(search) ||
          option.name.toLocaleLowerCase().includes(search) ||
          option.label.toLocaleLowerCase().includes(search),
      ),
    [search, states],
  );
  const indexedOptions = new Map(filtered.map((option, index) => [option.code, index]));

  function choose(option: StateOption | null) {
    setQuery(option ? stateOptionLabel(option) : "");
    setActiveIndex(-1);
    onChange(option?.code ?? "");
    setOpen(false);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      if (filtered.length) {
        setActiveIndex((current) => Math.min(current + 1, filtered.length - 1));
      }
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (filtered.length) setActiveIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter" && activeIndex >= 0 && filtered[activeIndex]) {
      event.preventDefault();
      choose(filtered[activeIndex]);
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
          aria-activedescendant={
            activeIndex >= 0 ? `${listboxId}-${filtered[activeIndex]?.code}` : undefined
          }
          aria-invalid={invalid}
          autoComplete="off"
          required
          value={query}
          onFocus={() => {
            setOpen(true);
            setActiveIndex(-1);
          }}
          onChange={(event) => {
            setQuery(event.target.value);
            setActiveIndex(-1);
            onChange("");
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          placeholder="Search by state name or abbreviation"
        />
        {query && (
          <button
            className="manager-combobox-clear"
            type="button"
            onClick={() => choose(null)}
            aria-label="Clear state"
          >
            <X size={14} />
          </button>
        )}
      </div>
      {open && (
        <div className="manager-combobox-results" id={listboxId} role="listbox">
          {GROUPS.map((group) => {
            const options = filtered.filter((option) => option.group === group.key);
            if (!options.length) return null;
            return (
              <div
                aria-label={group.label}
                className="state-combobox-group"
                key={group.key}
                role="group"
              >
                <div className="state-combobox-group-label">{group.label}</div>
                {options.map((option) => {
                  const index = indexedOptions.get(option.code) ?? -1;
                  return (
                    <button
                      className={`manager-combobox-option${index === activeIndex ? " active" : ""}`}
                      id={`${listboxId}-${option.code}`}
                      key={option.code}
                      type="button"
                      role="option"
                      aria-selected={option.code === selected?.code}
                      onMouseDown={(event) => event.preventDefault()}
                      onMouseEnter={() => setActiveIndex(index)}
                      onClick={() => choose(option)}
                    >
                      {stateOptionLabel(option)}
                    </button>
                  );
                })}
              </div>
            );
          })}
          {filtered.length === 0 && (
            <div className="manager-combobox-status">No matching states or territories.</div>
          )}
        </div>
      )}
    </div>
  );
}
