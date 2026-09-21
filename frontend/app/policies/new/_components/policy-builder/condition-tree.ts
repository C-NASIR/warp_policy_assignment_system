import type { Condition, ConditionGroup } from "@/lib/types";

export const MAX_CONDITION_GROUP_DEPTH = 3;
export const MAX_CONDITION_GROUPS = 20;
export const MAX_POLICY_CONDITIONS = 50;
export const MAX_COMPILED_CLAUSES = 200;

export type BuilderCondition = Condition & { rowId: number };

export type BuilderConditionGroup = {
  groupId: number;
  logical_operator: "and" | "or";
  conditions: BuilderCondition[];
  child_groups: BuilderConditionGroup[];
};

export type ConditionTreeStats = {
  groups: number;
  conditions: number;
  depth: number;
  compiledClauses: number;
};

export function defaultCondition(): Omit<BuilderCondition, "rowId"> {
  return {
    field: "",
    operator: "=",
    value: "",
  };
}

export function initializeConditionTree(
  source: ConditionGroup | undefined,
  includeDefaultCondition: boolean,
): BuilderConditionGroup {
  let nextGroupId = 1;
  let nextConditionId = 1;

  function visit(group: ConditionGroup): BuilderConditionGroup {
    return {
      groupId: nextGroupId++,
      logical_operator: group.logical_operator,
      conditions: group.conditions.map((condition) => ({
        ...condition,
        rowId: nextConditionId++,
      })),
      child_groups: group.child_groups.map(visit),
    };
  }

  if (source) return visit(source);
  return {
    groupId: nextGroupId,
    logical_operator: "and",
    conditions: includeDefaultCondition ? [{ rowId: nextConditionId, ...defaultCondition() }] : [],
    child_groups: [],
  };
}

export function serializeConditionTree(group: BuilderConditionGroup): ConditionGroup {
  return {
    logical_operator: group.logical_operator,
    conditions: group.conditions.map(({ field, operator, value }) => ({
      field,
      operator,
      value,
    })),
    child_groups: group.child_groups.map(serializeConditionTree),
  };
}

export function conditionTreeStats(root: BuilderConditionGroup): ConditionTreeStats {
  const structural = structuralStats(root, 1);
  return {
    ...structural,
    compiledClauses: compiledClauseCount(root),
  };
}

export function conditionTreeValidationError(root: BuilderConditionGroup): string | null {
  if (containsEmptyGroup(root)) return "Every condition group must contain a condition or group.";
  if (containsIncompleteCondition(root)) {
    return "Complete the highlighted fields before previewing this policy.";
  }

  const stats = conditionTreeStats(root);
  if (stats.depth > MAX_CONDITION_GROUP_DEPTH) {
    return `Condition groups may be at most ${MAX_CONDITION_GROUP_DEPTH} levels deep.`;
  }
  if (stats.groups > MAX_CONDITION_GROUPS) {
    return `A policy may contain at most ${MAX_CONDITION_GROUPS} condition groups.`;
  }
  if (stats.conditions > MAX_POLICY_CONDITIONS) {
    return `A policy may contain at most ${MAX_POLICY_CONDITIONS} conditions.`;
  }
  if (stats.compiledClauses > MAX_COMPILED_CLAUSES) {
    return `This policy expands to more than ${MAX_COMPILED_CLAUSES} evaluation clauses. Simplify its groups before previewing.`;
  }
  return null;
}

export function maximumBuilderIds(root: BuilderConditionGroup) {
  let groupId = root.groupId;
  let conditionId = 0;

  function visit(group: BuilderConditionGroup) {
    groupId = Math.max(groupId, group.groupId);
    for (const condition of group.conditions) {
      conditionId = Math.max(conditionId, condition.rowId);
    }
    group.child_groups.forEach(visit);
  }

  visit(root);
  return { groupId, conditionId };
}

function structuralStats(
  root: BuilderConditionGroup,
  depth: number,
): Omit<ConditionTreeStats, "compiledClauses"> {
  let groups = 1;
  let conditions = root.conditions.length;
  let maximumDepth = depth;
  for (const child of root.child_groups) {
    const childStats = structuralStats(child, depth + 1);
    groups += childStats.groups;
    conditions += childStats.conditions;
    maximumDepth = Math.max(maximumDepth, childStats.depth);
  }
  return { groups, conditions, depth: maximumDepth };
}

function compiledClauseCount(root: BuilderConditionGroup): number {
  const operandCounts = [
    ...root.conditions.map(() => 1),
    ...root.child_groups.map(compiledClauseCount),
  ];
  if (operandCounts.length === 0) return 0;
  if (root.logical_operator === "or") {
    return Math.min(
      operandCounts.reduce((total, count) => total + count, 0),
      MAX_COMPILED_CLAUSES + 1,
    );
  }

  let clauseCount = 1;
  for (const operandCount of operandCounts) {
    clauseCount *= operandCount;
    if (clauseCount > MAX_COMPILED_CLAUSES) return MAX_COMPILED_CLAUSES + 1;
  }
  return clauseCount;
}

function containsEmptyGroup(root: BuilderConditionGroup): boolean {
  return (
    (root.conditions.length === 0 && root.child_groups.length === 0) ||
    root.child_groups.some(containsEmptyGroup)
  );
}

function containsIncompleteCondition(root: BuilderConditionGroup): boolean {
  return (
    root.conditions.some((condition) => !condition.field || !condition.value.trim()) ||
    root.child_groups.some(containsIncompleteCondition)
  );
}
