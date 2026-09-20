import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { StateOption } from "@/lib/types";
import { StateCombobox } from "./state-combobox";

const states: StateOption[] = [
  { code: "CA", name: "California", label: "California", group: "states" },
  { code: "TX", name: "Texas", label: "Texas", group: "states" },
  { code: "GU", name: "Guam", label: "Guam", group: "territories" },
];

describe("StateCombobox", () => {
  it("searches state and jurisdiction options and displays the chosen selection", () => {
    const onChange = vi.fn();
    render(<StateCombobox states={states} value="" onChange={onChange} />);

    const input = screen.getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "guam" } });

    expect(screen.getByRole("option", { name: "Guam · GU" })).toBeVisible();
    expect(screen.queryByRole("option", { name: "California · CA" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("option", { name: "Guam · GU" }));

    expect(onChange).toHaveBeenLastCalledWith("GU");
  });

  it("reflects externally changed selections and marks the selected option", () => {
    const onChange = vi.fn();
    const { rerender } = render(<StateCombobox states={states} value="CA" onChange={onChange} />);

    const input = screen.getByRole("combobox");
    expect(input).toHaveValue("California · CA");

    rerender(<StateCombobox states={states} value="GU" onChange={onChange} />);

    expect(input).toHaveValue("Guam · GU");
    fireEvent.focus(input);
    expect(screen.getByRole("option", { name: "Guam · GU" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });
});
