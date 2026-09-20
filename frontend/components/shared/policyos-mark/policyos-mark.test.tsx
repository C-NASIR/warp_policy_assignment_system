import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PolicyOSMark } from "./policyos-mark";

describe("PolicyOSMark", () => {
  it("is decorative when the adjacent lockup names the product", () => {
    const { container } = render(<PolicyOSMark size={28} />);
    const image = container.querySelector("img");

    expect(image).toHaveAttribute("alt", "");
    expect(image).toHaveAttribute("aria-hidden", "true");
    expect(image).toHaveAttribute("width", "28");
    expect(image).toHaveAttribute("height", "28");
  });

  it("can expose an accessible name when used by itself", () => {
    const { getByRole } = render(<PolicyOSMark decorative={false} label="PolicyOS home" />);

    expect(getByRole("img", { name: "PolicyOS home" })).not.toHaveAttribute("aria-hidden");
  });
});
