import { describe, expect, it } from "vitest";
import type { ConditionGroup } from "@/lib/types";
import {
  MAX_COMPILED_CLAUSES,
  conditionTreeStats,
  conditionTreeValidationError,
  initializeConditionTree,
  serializeConditionTree,
  type BuilderConditionGroup,
} from "./condition-tree";

const condition = (field: string, value: string) => ({
  field,
  operator: "=" as const,
  value,
});

describe("policy condition trees", () => {
  it("round-trips multiple sibling groups and three levels without dropping branches", () => {
    const source: ConditionGroup = {
      logical_operator: "and",
      conditions: [condition("employee_type", "regular")],
      child_groups: [
        {
          logical_operator: "or",
          conditions: [condition("state", "CA"), condition("state", "NY")],
          child_groups: [],
        },
        {
          logical_operator: "and",
          conditions: [condition("department", "Engineering")],
          child_groups: [
            {
              logical_operator: "or",
              conditions: [condition("location", "Remote"), condition("location", "Chicago")],
              child_groups: [],
            },
          ],
        },
      ],
    };

    const builderTree = initializeConditionTree(source, true);

    expect(serializeConditionTree(builderTree)).toEqual(source);
    expect(conditionTreeStats(builderTree)).toMatchObject({
      groups: 4,
      conditions: 6,
      depth: 3,
    });
    expect(conditionTreeValidationError(builderTree)).toBeNull();
  });

  it("rejects trees whose AND/OR normalization exceeds the clause limit", () => {
    let conditionId = 1;
    let groupId = 1;
    const orGroup = (): BuilderConditionGroup => ({
      groupId: groupId++,
      logical_operator: "or",
      conditions: ["CA", "NY", "TX"].map((value) => ({
        rowId: conditionId++,
        ...condition("state", value),
      })),
      child_groups: [],
    });
    const tree: BuilderConditionGroup = {
      groupId: groupId++,
      logical_operator: "and",
      conditions: [],
      child_groups: Array.from({ length: 5 }, orGroup),
    };

    expect(conditionTreeStats(tree).compiledClauses).toBe(MAX_COMPILED_CLAUSES + 1);
    expect(conditionTreeValidationError(tree)).toMatch(/more than 200 evaluation clauses/i);
  });
});
