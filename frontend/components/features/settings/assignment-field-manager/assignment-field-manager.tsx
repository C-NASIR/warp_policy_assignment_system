"use client";

import { Braces, Check, CircleAlert, Plus, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, Button, DataTable, SelectInput, TablePanel, TextInput } from "@/components/ui";
import type { AssignmentField } from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";
import valueStyles from "@/components/shared/styles/value-text.module.css";

export function AssignmentFieldManager({
  initialFields,
  canManage = true,
}: {
  initialFields: AssignmentField[];
  canManage?: boolean;
}) {
  const [fields, setFields] = useState(initialFields);
  const [search, setSearch] = useState("");
  const [cardinality, setCardinality] = useState("all");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [newCardinality, setNewCardinality] = useState<"one" | "many">("one");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useModalAccessibility(open, () => setOpen(false));
  const filtered = useMemo(
    () =>
      fields.filter(
        (field) =>
          field.name.toLowerCase().includes(search.toLowerCase()) &&
          (cardinality === "all" || field.cardinality === cardinality),
      ),
    [cardinality, fields, search],
  );

  async function createField() {
    const normalized = name.trim();
    if (!normalized) {
      setError("Enter an assignment field name.");
      return;
    }
    if (fields.some((field) => field.name.toLowerCase() === normalized.toLowerCase())) {
      setError("An assignment field with this name already exists.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const response = await fetch("/api/backend/assignment-fields", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: normalized,
          cardinality: newCardinality,
          conflict_resolution: "priority",
        }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          result.error?.message ?? result.detail ?? "The assignment field could not be created.",
        );
      const created = result as AssignmentField;
      setFields((current) => [...current, created]);
      setOpen(false);
      setName("");
      setNewCardinality("one");
      setNotice(`${normalized} is ready for policy assignments.`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create the assignment field.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">System setup</p>
          <h1>Assignment fields</h1>
          <p className="page-subtitle">
            Define assignable policy categories and the conflict behavior each category requires.
          </p>
        </div>
        {canManage && (
          <Button
            onClick={() => {
              setOpen(true);
              setError("");
            }}
          >
            <Plus size={15} /> Create field
          </Button>
        )}
      </div>
      {notice && (
        <div className="success-banner" role="status">
          <Check size={14} />
          {notice}
        </div>
      )}
      <div className="toolbar">
        <div className="toolbar-left">
          <label className="search-box">
            <Search size={14} />
            <TextInput
              className="input"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search assignment fields"
              aria-label="Search assignment fields"
            />
          </label>
          <SelectInput
            className="filter-select"
            value={cardinality}
            onChange={(event) => setCardinality(event.target.value)}
            aria-label="Filter by cardinality"
          >
            <option value="all">All cardinalities</option>
            <option value="one">One value</option>
            <option value="many">Many values</option>
          </SelectInput>
        </div>
        <span className="results-count">{filtered.length} fields</span>
      </div>
      <TablePanel>
        <DataTable>
          <thead>
            <tr>
              <th>Assignment field</th>
              <th>Cardinality</th>
              <th>Resolution</th>
              <th>Behavior</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((field) => (
              <tr key={field.id}>
                <td>
                  <span className="person-cell">
                    <span className="avatar">
                      <Braces size={14} />
                    </span>
                    <span className="primary-cell">{field.name}</span>
                  </span>
                </td>
                <td>
                  <Badge tone="accent">
                    {field.cardinality === "one" ? "One value" : "Many values"}
                  </Badge>
                </td>
                <td>{field.cardinality === "one" ? "Highest priority wins" : "Set union"}</td>
                <td>
                  <span className={`secondary-cell ${valueStyles.flush}`}>
                    {field.cardinality === "one"
                      ? "One final value per employee"
                      : "Unique values from every matching rule"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTable>
        {filtered.length === 0 && (
          <div className="empty-state compact">No assignment fields match those filters.</div>
        )}
        <div className="pagination-footer">
          <span>{fields.length} total fields</span>
          <span>Cardinality is fixed after creation</span>
        </div>
      </TablePanel>
      {open && (
        <div className="modal-backdrop" role="presentation">
          <section
            className="form-dialog"
            role="dialog"
            aria-modal="true"
            aria-label="Create assignment field"
          >
            <div className="modal-head">
              <div>
                <h2>Create assignment field</h2>
                <div className="panel-caption">
                  Choose carefully—cardinality defines resolution behavior.
                </div>
              </div>
              <button className="icon-button" onClick={() => setOpen(false)} aria-label="Close">
                <X size={16} />
              </button>
            </div>
            <div className="form-section">
              {error && (
                <div className="error-banner">
                  <CircleAlert size={13} />
                  {error}
                </div>
              )}
              <label className="field">
                <span className="field-label">
                  Field name <span className="required">Required</span>
                </span>
                <input
                  className="input"
                  autoFocus
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    setError("");
                  }}
                  placeholder="e.g. Holiday calendar"
                />
              </label>
              <fieldset className="choice-grid">
                <legend className="field-label">Cardinality</legend>
                <label className={`choice-card${newCardinality === "one" ? " selected" : ""}`}>
                  <input
                    type="radio"
                    name="cardinality"
                    value="one"
                    checked={newCardinality === "one"}
                    onChange={() => setNewCardinality("one")}
                  />
                  <span>
                    <strong>One value</strong>
                    <small>
                      Competing policies resolve by priority, then deterministically by version.
                    </small>
                  </span>
                </label>
                <label className={`choice-card${newCardinality === "many" ? " selected" : ""}`}>
                  <input
                    type="radio"
                    name="cardinality"
                    value="many"
                    checked={newCardinality === "many"}
                    onChange={() => setNewCardinality("many")}
                  />
                  <span>
                    <strong>Many values</strong>
                    <small>Unique values from all matching policies are combined as a set.</small>
                  </span>
                </label>
              </fieldset>
            </div>
            <div className="form-footer">
              <span className="form-hint">
                New fields become available in the policy builder immediately.
              </span>
              <div className="heading-actions">
                <Button variant="secondary" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button disabled={saving} onClick={createField}>
                  {saving ? "Creating…" : "Create field"}
                </Button>
              </div>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
