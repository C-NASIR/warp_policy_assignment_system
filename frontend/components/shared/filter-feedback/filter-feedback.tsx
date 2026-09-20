"use client";

import { LoaderCircle, X } from "lucide-react";
import type { ReactNode } from "react";

export type AppliedFilter = {
  key: string;
  label: string;
};

export function AppliedFilterRow({
  filters,
  onClear,
  onRemove,
}: {
  filters: AppliedFilter[];
  onClear(): void;
  onRemove(key: string): void;
}) {
  if (filters.length === 0) return null;

  return (
    <div className="active-filter-row" aria-label="Applied filters">
      <span>Applied</span>
      {filters.map((filter) => (
        <button
          className="filter-chip"
          type="button"
          key={filter.key}
          onClick={() => onRemove(filter.key)}
          aria-label={`Remove ${filter.label} filter`}
        >
          {filter.label} <X size={11} aria-hidden="true" />
        </button>
      ))}
      <button className="clear-filters" type="button" onClick={onClear}>
        Clear all
      </button>
    </div>
  );
}

export function DirectoryResultsStatus({
  children,
  pending,
}: {
  children: ReactNode;
  pending: boolean;
}) {
  return (
    <span className="results-count directory-results-status" role="status" aria-live="polite">
      {pending ? (
        <>
          <LoaderCircle className="filter-loading-icon" size={13} aria-hidden="true" />
          Updating results…
        </>
      ) : (
        children
      )}
    </span>
  );
}

export function DirectoryLoadingState({ label }: { label: string }) {
  return (
    <div className="directory-loading-state" role="status" aria-live="polite">
      <LoaderCircle className="filter-loading-icon" size={20} aria-hidden="true" />
      <strong>{label}</strong>
      <span>The latest results will appear here when they are ready.</span>
    </div>
  );
}
