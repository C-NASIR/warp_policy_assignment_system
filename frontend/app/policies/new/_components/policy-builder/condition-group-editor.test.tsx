import { useRef, useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConditionGroupEditor } from "./condition-group-editor";
import {
  conditionTreeStats,
  defaultCondition,
  type BuilderCondition,
  type BuilderConditionGroup,
} from "./condition-tree";

function EditorHarness() {
  const [tree, setTree] = useState<BuilderConditionGroup>({
    groupId: 1,
    logical_operator: "and",
    conditions: [{ rowId: 1, ...defaultCondition() }],
    child_groups: [],
  });
  const ids = useRef({ group: 1, condition: 1 });
  const createCondition = (): BuilderCondition => ({
    rowId: ++ids.current.condition,
    ...defaultCondition(),
  });
  const createGroup = (): BuilderConditionGroup => ({
    groupId: ++ids.current.group,
    logical_operator: "or",
    conditions: [createCondition()],
    child_groups: [],
  });

  return (
    <ConditionGroupEditor
      group={tree}
      conditionFields={[]}
      employees={[]}
      referenceData={{ departments: [], employee_types: [], states: [] }}
      validationAttempted={false}
      stats={conditionTreeStats(tree)}
      onChange={setTree}
      createCondition={createCondition}
      createGroup={createGroup}
    />
  );
}

describe("ConditionGroupEditor", () => {
  it("adds multiple sibling groups", () => {
    render(<EditorHarness />);

    fireEvent.click(screen.getByRole("button", { name: "Add nested group" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Add nested group" })[1]);

    expect(screen.getAllByText("Level 2 of 3")).toHaveLength(2);
  });

  it("allows three levels and explains why deeper nesting is disabled", () => {
    render(<EditorHarness />);

    fireEvent.click(screen.getByRole("button", { name: "Add nested group" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Add nested group" })[0]);

    expect(screen.getByText("Level 3 of 3")).toBeInTheDocument();
    expect(screen.getByText("Maximum nesting depth of 3 levels reached")).toBeInTheDocument();
    expect(screen.getByTitle("Maximum nesting depth of 3 levels reached")).toBeDisabled();
  });
});
