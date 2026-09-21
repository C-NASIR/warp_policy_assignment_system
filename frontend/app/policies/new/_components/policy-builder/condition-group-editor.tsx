"use client";

import { Plus, Trash2 } from "lucide-react";
import { ConditionRow } from "./condition-row";
import {
  MAX_CONDITION_GROUP_DEPTH,
  MAX_CONDITION_GROUPS,
  MAX_POLICY_CONDITIONS,
  type BuilderCondition,
  type BuilderConditionGroup,
  type ConditionTreeStats,
} from "./condition-tree";
import { Badge } from "@/components/ui";
import type { ConditionField, Employee, EmployeeReferenceData } from "@/lib/types";
import styles from "./policy-builder.module.css";

export function ConditionGroupEditor({
  group,
  depth = 1,
  conditionFields,
  employees,
  referenceData,
  validationAttempted,
  stats,
  onChange,
  onRemove,
  removeDisabled = false,
  createCondition,
  createGroup,
}: {
  group: BuilderConditionGroup;
  depth?: number;
  conditionFields: ConditionField[];
  employees: Employee[];
  referenceData: EmployeeReferenceData;
  validationAttempted: boolean;
  stats: ConditionTreeStats;
  onChange(group: BuilderConditionGroup): void;
  onRemove?: () => void;
  removeDisabled?: boolean;
  createCondition(): BuilderCondition;
  createGroup(): BuilderConditionGroup;
}) {
  const canAddCondition = stats.conditions < MAX_POLICY_CONDITIONS;
  const canAddGroup =
    depth < MAX_CONDITION_GROUP_DEPTH &&
    stats.groups < MAX_CONDITION_GROUPS &&
    stats.conditions < MAX_POLICY_CONDITIONS;
  const groupLimitReason =
    depth >= MAX_CONDITION_GROUP_DEPTH
      ? `Maximum nesting depth of ${MAX_CONDITION_GROUP_DEPTH} levels reached`
      : stats.groups >= MAX_CONDITION_GROUPS
        ? `Maximum of ${MAX_CONDITION_GROUPS} condition groups reached`
        : stats.conditions >= MAX_POLICY_CONDITIONS
          ? `Maximum of ${MAX_POLICY_CONDITIONS} conditions reached`
          : undefined;

  return (
    <div className={`rule-group${depth > 1 ? " nested" : ""}`}>
      <div className="rule-group-head">
        <label className="logical-picker">
          {depth === 1 ? "Employees matching" : "Group matching"}{" "}
          <select
            aria-label={depth === 1 ? "Root group logic" : `Group level ${depth} logic`}
            className="select"
            value={group.logical_operator}
            onChange={(event) =>
              onChange({
                ...group,
                logical_operator: event.target.value as "and" | "or",
              })
            }
          >
            <option value="and">ALL</option>
            <option value="or">ANY</option>
          </select>{" "}
          of
        </label>
        {depth === 1 ? (
          <Badge tone="accent">Backend evaluated</Badge>
        ) : (
          <div className={styles.groupHeaderActions}>
            <span className={styles.depthLabel}>
              Level {depth} of {MAX_CONDITION_GROUP_DEPTH}
            </span>
            <button
              className="remove-button"
              type="button"
              disabled={removeDisabled}
              onClick={onRemove}
              title={
                removeDisabled ? "A group must contain at least one condition or group" : undefined
              }
              aria-label={`Remove group at level ${depth}`}
            >
              <Trash2 size={13} />
            </button>
          </div>
        )}
      </div>

      {group.conditions.map((condition) => (
        <ConditionRow
          key={condition.rowId}
          condition={condition}
          conditionFields={conditionFields}
          employees={employees}
          referenceData={referenceData}
          validationAttempted={validationAttempted}
          errorMessageId="policy-form-error"
          removeDisabled={group.conditions.length === 1 && group.child_groups.length === 0}
          removeLabel={`Remove condition from group level ${depth}`}
          onChange={(patch) =>
            onChange({
              ...group,
              conditions: group.conditions.map((item) =>
                item.rowId === condition.rowId ? { ...item, ...patch } : item,
              ),
            })
          }
          onRemove={() =>
            onChange({
              ...group,
              conditions: group.conditions.filter((item) => item.rowId !== condition.rowId),
            })
          }
        />
      ))}

      {group.child_groups.map((child) => (
        <ConditionGroupEditor
          key={child.groupId}
          group={child}
          depth={depth + 1}
          conditionFields={conditionFields}
          employees={employees}
          referenceData={referenceData}
          validationAttempted={validationAttempted}
          stats={stats}
          createCondition={createCondition}
          createGroup={createGroup}
          onChange={(nextChild) =>
            onChange({
              ...group,
              child_groups: group.child_groups.map((item) =>
                item.groupId === child.groupId ? nextChild : item,
              ),
            })
          }
          onRemove={() =>
            onChange({
              ...group,
              child_groups: group.child_groups.filter((item) => item.groupId !== child.groupId),
            })
          }
          removeDisabled={group.conditions.length === 0 && group.child_groups.length === 1}
        />
      ))}

      <div className="heading-actions">
        <button
          className="text-button"
          type="button"
          disabled={!canAddCondition}
          title={
            canAddCondition ? undefined : `Maximum of ${MAX_POLICY_CONDITIONS} conditions reached`
          }
          onClick={() =>
            onChange({ ...group, conditions: [...group.conditions, createCondition()] })
          }
        >
          <Plus size={13} /> Add condition
        </button>
        <button
          className="text-button"
          type="button"
          disabled={!canAddGroup}
          title={groupLimitReason}
          onClick={() =>
            onChange({ ...group, child_groups: [...group.child_groups, createGroup()] })
          }
        >
          <Plus size={13} /> Add nested group
        </button>
        {!canAddGroup && <span className={styles.limitHint}>{groupLimitReason}</span>}
      </div>
    </div>
  );
}
