"use client";

import { Braces, Check, CircleAlert, Pencil, Plus, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, Button, DataTable, Panel, SelectInput, TextInput } from "@/components/ui";
import type { AssignmentField } from "@/lib/types";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";

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
  const [editingField, setEditingField] = useState<AssignmentField | null>(null);
  const [name, setName] = useState("");
  const [newCardinality, setNewCardinality] = useState<"one" | "many">("one");
  const [inputType, setInputType] = useState<"select" | "text">("select");
  const [optionsText, setOptionsText] = useState("");
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

  function openEditor(field?: AssignmentField) {
    setEditingField(field ?? null);
    setName(field?.name ?? "");
    setNewCardinality(field?.cardinality ?? "one");
    setInputType(field?.input.type ?? "select");
    setOptionsText(field?.input.options.map((option) => option.value).join("\n") ?? "");
    setError("");
    setOpen(true);
  }

  async function saveField() {
    const normalized = name.trim();
    if (!normalized) {
      setError("Enter an assignment field name.");
      return;
    }
    if (
      !editingField &&
      fields.some((field) => field.name.toLowerCase() === normalized.toLowerCase())
    ) {
      setError("An assignment field with this name already exists.");
      return;
    }
    const options = optionsText
      .split("\n")
      .map((option) => option.trim())
      .filter(Boolean);
    if (inputType === "select" && options.length === 0) {
      setError("Enter at least one allowed value.");
      return;
    }
    if (new Set(options.map((option) => option.toLowerCase())).size !== options.length) {
      setError("Allowed values must be unique.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const input = {
        type: inputType,
        options:
          inputType === "select" ? options.map((option) => ({ value: option, label: option })) : [],
      };
      const response = await fetch(
        editingField
          ? `/api/backend/assignment-fields/${editingField.id}`
          : "/api/backend/assignment-fields",
        {
          method: editingField ? "PATCH" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(
            editingField
              ? { input }
              : {
                  name: normalized,
                  cardinality: newCardinality,
                  conflict_resolution: "priority",
                  input,
                },
          ),
        },
      );
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(result.error?.message ?? "The assignment field could not be saved.");
      const saved = result as AssignmentField;
      setFields((current) =>
        editingField
          ? current.map((field) => (field.id === saved.id ? saved : field))
          : [...current, saved],
      );
      setOpen(false);
      setName("");
      setNewCardinality("one");
      setInputType("select");
      setOptionsText("");
      setEditingField(null);
      setNotice(
        editingField
          ? `${normalized}'s allowed values were updated.`
          : `${normalized} is ready for policy assignments.`,
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save the assignment field.");
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
          <Button onClick={() => openEditor()}>
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
      <Panel as="div" clipped>
        <DataTable>
          <thead>
            <tr>
              <th>Assignment field</th>
              <th>Cardinality</th>
              <th>Resolution</th>
              <th>Allowed values</th>
              <th>Behavior</th>
              {canManage && <th>Actions</th>}
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
                  {field.input.type === "select"
                    ? `${field.input.options.length} controlled options`
                    : "Free text"}
                </td>
                <td>
                  <span className="secondary-cell flush">
                    {field.cardinality === "one"
                      ? "One final value per employee"
                      : "Unique values from every matching rule"}
                  </span>
                </td>
                {canManage && (
                  <td>
                    <button
                      className="icon-button"
                      onClick={() => openEditor(field)}
                      aria-label={`Edit ${field.name} allowed values`}
                    >
                      <Pencil size={13} />
                    </button>
                  </td>
                )}
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
      </Panel>
      {open && (
        <div className="modal-backdrop" role="presentation">
          <section
            className="form-dialog"
            role="dialog"
            aria-modal="true"
            aria-label={editingField ? "Edit assignment field values" : "Create assignment field"}
          >
            <div className="modal-head">
              <div>
                <h2>{editingField ? "Edit allowed values" : "Create assignment field"}</h2>
                <div className="panel-caption">
                  {editingField
                    ? "Update the values available for this assignment field."
                    : "Choose carefully—cardinality defines resolution behavior."}
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
                  Field name
                  <span className="required">
                    {editingField ? "Fixed after creation" : "Required"}
                  </span>
                </span>
                <input
                  className="input"
                  autoFocus
                  disabled={Boolean(editingField)}
                  value={name}
                  onChange={(event) => {
                    setName(event.target.value);
                    setError("");
                  }}
                  placeholder="e.g. Holiday calendar"
                />
              </label>
              {editingField ? (
                <div className="fixed-cardinality">
                  <span className="field-label">
                    Cardinality <span className="required">Fixed after creation</span>
                  </span>
                  <div className="fixed-cardinality-value">
                    <strong>{newCardinality === "one" ? "One value" : "Many values"}</strong>
                    <small>
                      {newCardinality === "one"
                        ? "Competing policies resolve by priority, then deterministically by version."
                        : "Unique values from all matching policies are combined as a set."}
                    </small>
                  </div>
                </div>
              ) : (
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
              )}
              <label className="field">
                <span className="field-label">Value control</span>
                <select
                  className="select"
                  value={inputType}
                  onChange={(event) => setInputType(event.target.value as "select" | "text")}
                >
                  <option value="select">Controlled options</option>
                  <option value="text">Free text</option>
                </select>
              </label>
              {inputType === "select" && (
                <label className="field">
                  <span className="field-label">
                    Allowed values <span className="required">Required</span>
                  </span>
                  <textarea
                    className="textarea"
                    rows={6}
                    value={optionsText}
                    onChange={(event) => {
                      setOptionsText(event.target.value);
                      setError("");
                    }}
                    placeholder={"Enter one allowed value per line"}
                  />
                  <span className="form-hint">
                    Policies and overrides must choose one of these exact values.
                  </span>
                </label>
              )}
            </div>
            <div className="form-footer assignment-field-form-footer">
              <span className="form-hint">
                {editingField
                  ? "Existing policy history keeps its stored values. New changes use this list."
                  : "New fields become available in the policy builder immediately."}
              </span>
              <div className="heading-actions">
                <Button variant="secondary" onClick={() => setOpen(false)}>
                  Cancel
                </Button>
                <Button disabled={saving} onClick={saveField}>
                  {saving ? "Saving…" : editingField ? "Save values" : "Create field"}
                </Button>
              </div>
            </div>
          </section>
        </div>
      )}
    </>
  );
}
