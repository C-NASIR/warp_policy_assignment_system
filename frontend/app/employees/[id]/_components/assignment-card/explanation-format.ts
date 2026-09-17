import { titleCase } from "@/lib/format";
import type {
  AssignmentCandidate,
  AssignmentConditionEvidence,
  AssignmentExplanation,
  AssignmentOrigin,
  CurrentAssignment,
} from "@/lib/types";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const ISO_DURATION = /^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?$/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isValidDate(value: string) {
  return ISO_DATE.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`));
}

export function formatExplanationDate(value: string | null | undefined) {
  if (!value || !isValidDate(value)) return value || "Unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function unit(value: number, label: string) {
  return `${value} ${label}${value === 1 ? "" : "s"}`;
}

export function formatIsoDuration(value: string) {
  const match = ISO_DURATION.exec(value);
  if (!match) return null;
  const parts = [
    [Number(match[1] ?? 0), "year"],
    [Number(match[2] ?? 0), "month"],
    [Number(match[3] ?? 0), "week"],
    [Number(match[4] ?? 0), "day"],
  ] as const;
  const rendered = parts
    .filter(([amount]) => amount > 0)
    .map(([amount, label]) => unit(amount, label));
  return rendered.length ? rendered.join(", ") : "0 days";
}

function daysInMonth(year: number, month: number) {
  return new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
}

function addCalendarParts(day: Date, years: number, months: number) {
  const year = day.getUTCFullYear() + years;
  const monthIndex = day.getUTCMonth() + months;
  const normalizedYear = year + Math.floor(monthIndex / 12);
  const normalizedMonth = ((monthIndex % 12) + 12) % 12;
  return new Date(
    Date.UTC(
      normalizedYear,
      normalizedMonth,
      Math.min(day.getUTCDate(), daysInMonth(normalizedYear, normalizedMonth)),
    ),
  );
}

function formatTenure(value: Record<string, unknown>) {
  const start = value.start_date;
  const evaluation = value.evaluation_date;
  if (typeof start !== "string" || typeof evaluation !== "string") return null;
  if (!isValidDate(start) || !isValidDate(evaluation)) return null;
  const startDate = new Date(`${start}T00:00:00Z`);
  const endDate = new Date(`${evaluation}T00:00:00Z`);
  if (endDate < startDate) return "Not yet started";

  let years = endDate.getUTCFullYear() - startDate.getUTCFullYear();
  if (addCalendarParts(startDate, years, 0) > endDate) years -= 1;
  let cursor = addCalendarParts(startDate, years, 0);
  let months = 0;
  while (months < 11 && addCalendarParts(cursor, 0, 1) <= endDate) {
    cursor = addCalendarParts(cursor, 0, 1);
    months += 1;
  }
  const days = Math.floor((endDate.getTime() - cursor.getTime()) / 86_400_000);
  const parts = [
    years ? unit(years, "year") : null,
    months ? unit(months, "month") : null,
    days ? unit(days, "day") : null,
  ].filter((part): part is string => part !== null);
  return parts.length ? parts.join(", ") : "Less than one day";
}

function preferredObjectLabel(value: Record<string, unknown>) {
  for (const key of ["display_label", "displayLabel", "label", "name"]) {
    if (typeof value[key] === "string" && value[key]) return value[key];
  }
  return null;
}

export function formatEvidenceValue(value: unknown, storedLabel?: string | null): string {
  if (storedLabel) return storedLabel;
  if (value === null || value === undefined || value === "") return "Unavailable";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return new Intl.NumberFormat("en-US").format(value);
  if (typeof value === "string") {
    const duration = formatIsoDuration(value);
    if (duration) return duration;
    if (isValidDate(value)) return formatExplanationDate(value);
    return value;
  }
  if (Array.isArray(value)) {
    if (!value.length) return "None";
    return value.map((item) => formatEvidenceValue(item)).join(", ");
  }
  if (isRecord(value)) {
    const tenure = formatTenure(value);
    if (tenure) return tenure;
    const label = preferredObjectLabel(value);
    const id = value.id ?? value.employee_id;
    if (label && (typeof id === "string" || typeof id === "number")) return `${label} (#${id})`;
    if (label) return label;
    if (typeof value.value !== "object" && value.value !== undefined) {
      return formatEvidenceValue(value.value);
    }
    const entries = Object.entries(value)
      .slice(0, 4)
      .map(([key, item]) => `${titleCase(key)}: ${formatEvidenceValue(item)}`);
    return entries.length ? entries.join("; ") : "Details unavailable";
  }
  return String(value);
}

export function operatorLabel(operator: string | undefined) {
  return (
    {
      "=": "is",
      "==": "is",
      "!=": "is not",
      ">": "is more than",
      ">=": "is at least",
      "<": "is less than",
      "<=": "is at most",
      in: "is one of",
      not_in: "is not one of",
    }[operator ?? ""] ?? titleCase(operator || "matches")
  );
}

export function conditionLabel(condition: AssignmentConditionEvidence) {
  return `${titleCase(condition.field || "Condition")} ${operatorLabel(condition.operator)} ${formatEvidenceValue(condition.expected, condition.expected_label)}`;
}

export function actualConditionValue(condition: AssignmentConditionEvidence) {
  const value = formatEvidenceValue(condition.actual, condition.actual_label);
  if (
    (condition.field === "manager_id" || condition.field === "employee_id") &&
    /^\d+$/.test(value)
  ) {
    return `Employee #${value}`;
  }
  return value;
}

function stableValue(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableValue).join(",")}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${key}:${stableValue(value[key])}`)
      .join(",")}}`;
  }
  return String(value);
}

export type EvidenceClause = {
  key: string;
  conditions: AssignmentConditionEvidence[];
};

export function uniqueEvidenceClauses(origins: AssignmentOrigin[] | undefined): EvidenceClause[] {
  const seen = new Set<string>();
  const clauses: EvidenceClause[] = [];
  for (const origin of origins ?? []) {
    if (origin.type !== "condition_match") continue;
    for (const clause of origin.matched_clauses ?? []) {
      const conditions = (clause.conditions ?? []).filter(isConditionEvidence);
      const key = stableValue(conditions);
      if (!conditions.length || seen.has(key)) continue;
      seen.add(key);
      clauses.push({ key, conditions });
    }
  }
  return clauses;
}

function isConditionEvidence(value: unknown): value is AssignmentConditionEvidence {
  return isRecord(value) && ("actual" in value || "expected" in value);
}

export function groupOrigins(origins: AssignmentOrigin[] | undefined) {
  const seen = new Set<string>();
  return (origins ?? []).filter((origin) => {
    if (origin.type !== "group") return false;
    const key = `${origin.group_id ?? ""}:${origin.group_name ?? ""}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function candidateOutcomeLabel(candidate: AssignmentCandidate) {
  if (candidate.outcome === "selected" || candidate.selected) return "Selected";
  if (candidate.outcome === "lower_priority") return "Lower priority";
  if (candidate.outcome === "duplicate_value") return "Duplicate value";
  return titleCase(candidate.outcome || "Not selected");
}

export function candidateReason(candidate: AssignmentCandidate, winnerPriority?: number | null) {
  if (candidate.outcome === "selected" || candidate.selected) {
    return candidate.priority == null
      ? "Selected as the recorded source"
      : `Selected — priority ${candidate.priority}`;
  }
  if (candidate.outcome === "duplicate_value") {
    return "Same value — deduplicated; the higher-priority source was retained";
  }
  if (candidate.outcome === "lower_priority") {
    return candidate.priority == null
      ? "Not selected — lower priority"
      : `Not selected — priority ${candidate.priority} is lower${winnerPriority == null ? "" : ` than ${winnerPriority}`}`;
  }
  return candidate.outcome ? candidateOutcomeLabel(candidate) : "Not selected";
}

export function originText(origins: AssignmentOrigin[] | undefined) {
  const groups = groupOrigins(origins).map((origin) => origin.group_name || "an employee group");
  const direct = uniqueEvidenceClauses(origins).length > 0;
  const persisted = (origins ?? []).some((origin) => origin.type === "persisted_policy_link");
  const parts = [];
  if (direct) parts.push("Direct condition match");
  if (groups.length) parts.push(`Through ${groups.join(" and ")}`);
  if (persisted && !parts.length) parts.push("Recorded policy link");
  return parts.join("; ") || "Origin unavailable";
}

function firstMatchedFact(explanation: AssignmentExplanation) {
  const condition = uniqueEvidenceClauses(explanation.origins)[0]?.conditions[0];
  if (!condition) return null;
  const actual = actualConditionValue(condition);
  if (condition.field === "state") return `is based in ${actual}`;
  if (condition.field === "tenure") return `has ${actual} of tenure`;
  return `matches ${titleCase(condition.field || "a condition")}: ${actual}`;
}

export function explanationSummary(assignment: CurrentAssignment) {
  const explanation = assignment.explanation ?? {};
  const selection = explanation.selection;
  if (assignment.source_override_id !== null || explanation.reason === "manual_override") {
    const replaced = selection?.replaced_policy_assignments ?? [];
    if (!replaced.length) {
      return `This manual override assigned ${assignment.value}. No policy value existed to replace.`;
    }
    const descriptions = replaced.map((item) =>
      item.policy_name
        ? `${item.value ?? "a value"} from ${item.policy_name}`
        : `${item.value ?? "a policy value"} from a policy`,
    );
    return `This manual override assigned ${assignment.value} and replaced ${joinList(descriptions)}.`;
  }

  const policyName = explanation.policy?.name || "The recorded policy";
  const candidates = selection?.candidates ?? [];
  const duplicate = candidates.find((candidate) => candidate.outcome === "duplicate_value");
  if (duplicate) {
    return `${candidates.length} policies supplied ${assignment.value}. ${policyName} is recorded as the source${selection?.priority == null ? "" : ` because it has the higher priority (${selection.priority})`}.`;
  }
  const lower = candidates.find((candidate) => candidate.outcome === "lower_priority");
  const fact = firstMatchedFact(explanation);
  const groups = groupOrigins(explanation.origins);
  let matchReason = fact ? ` because this employee ${fact}` : "";
  if (groups.length && !fact) {
    matchReason = ` through ${joinList(groups.map((origin) => `${origin.group_name || "an employee"} group`))}`;
  } else if (groups.length) {
    matchReason += ` and also applies through ${joinList(groups.map((origin) => `${origin.group_name || "an employee"} group`))}`;
  }
  const winReason = lower
    ? ` It won over ${lower.policy_name || "another policy"}${selection?.priority == null || lower.priority == null ? "" : ` because priority ${selection.priority} is higher than priority ${lower.priority}`}.`
    : "";
  return `${policyName} assigned ${assignment.value}${matchReason}.${winReason}`;
}

export function joinList(items: string[]) {
  if (items.length < 2) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items.at(-1)}`;
}

export function cardinalityLabel(value: string | null | undefined) {
  if (value === "one") return "One value";
  if (value === "many") return "Multiple values";
  return value ? titleCase(value) : "Unavailable";
}

export function strategyLabel(value: string | null | undefined) {
  if (value === "priority") return "Highest priority wins";
  if (value === "set_union") return "Combine unique values";
  if (value === "override_replaces_policy") return "Manual value replaces policy results";
  return value ? titleCase(value) : "Unavailable";
}
