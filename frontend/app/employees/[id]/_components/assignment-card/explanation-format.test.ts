import { describe, expect, it } from "vitest";
import { formatEvidenceValue, formatIsoDuration } from "./explanation-format";

describe("evidence value formatting", () => {
  it("renders structured tenure as a real calendar duration", () => {
    const rendered = formatEvidenceValue({
      start_date: "2023-06-01",
      evaluation_date: "2026-09-16",
    });
    expect(rendered).toBe("3 years, 3 months, 15 days");
    expect(rendered).not.toContain("[object Object]");
  });

  it("renders ISO durations with correct grammar", () => {
    expect(formatIsoDuration("P3Y")).toBe("3 years");
    expect(formatIsoDuration("P1Y2M")).toBe("1 year, 2 months");
    expect(formatIsoDuration("P1D")).toBe("1 day");
  });

  it.each([
    ["plain text", "plain text"],
    [42, "42"],
    [true, "Yes"],
    [false, "No"],
    ["2026-09-16", "September 16, 2026"],
    [{ id: 17, name: "Priya Shah" }, "Priya Shah (#17)"],
    [null, "Unavailable"],
    [{ score: 7, status: "ready" }, "Score: 7; Status: ready"],
  ])("renders %j safely", (value, expected) => {
    const rendered = formatEvidenceValue(value);
    expect(rendered).toBe(expected);
    expect(rendered).not.toContain("[object Object]");
  });

  it("prefers a stored display label", () => {
    expect(formatEvidenceValue("IL", "Illinois")).toBe("Illinois");
  });
});
