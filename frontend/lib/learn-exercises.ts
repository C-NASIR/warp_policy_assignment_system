export type AssignmentResult = { field: string; values: string[]; explanation: string };

export type AveryExerciseInput = {
  state: string;
  department: string;
  employmentType: string;
  location: string;
  engineeringGroup: boolean;
  override: boolean;
};

export function resolveAveryAssignments({
  state,
  department,
  employmentType,
  location,
  engineeringGroup,
  override,
}: AveryExerciseInput): AssignmentResult[] {
  const results: AssignmentResult[] = [];
  const fullTime = employmentType === "Full-time";
  const california = state === "California";
  const engineering = department === "Engineering";

  const payCandidates = [
    ...(fullTime ? [{ value: "Semi-monthly", priority: 10, source: "US Employee Pay" }] : []),
    ...(california
      ? [{ value: "Bi-weekly", priority: 20, source: "California Pay Schedule" }]
      : []),
  ].sort((left, right) => right.priority - left.priority);

  if (override)
    results.push({
      field: "Pay schedule",
      values: ["Monthly"],
      explanation: payCandidates.length
        ? `Manual override replaces ${payCandidates.map((item) => item.value).join(" and ")}.`
        : "Manual override supplies the field without a policy result.",
    });
  else if (payCandidates[0])
    results.push({
      field: "Pay schedule",
      values: [payCandidates[0].value],
      explanation: `${payCandidates[0].source} wins at priority ${payCandidates[0].priority}.`,
    });

  if (fullTime)
    results.push({
      field: "Vacation policy",
      values: ["Standard PTO"],
      explanation: "Standard PTO matches Full-time.",
    });

  const access = [
    ...(fullTime ? ["1Password"] : []),
    ...(engineeringGroup || location === "Remote" ? ["GitHub", "Linear"] : []),
  ];
  if (access.length)
    results.push({
      field: "Application access",
      values: access,
      explanation:
        `${fullTime ? "Security Baseline matches directly. " : ""}${engineeringGroup ? "Engineering Access arrives through the explicit Engineering group." : location === "Remote" ? "Engineering Access matches Remote directly." : ""}`.trim(),
    });

  if (california)
    results.push({
      field: "Compliance training",
      values: ["CA Workplace Harassment"],
      explanation: "California Compliance matches state = California.",
    });
  if (engineering)
    results.push({
      field: "Equipment stipend",
      values: ["$1,000 annual"],
      explanation: "Engineering Equipment matches department = Engineering.",
    });
  return results;
}

export function resolvePriorityOutcome(
  cardinality: "one" | "many",
  californiaPriority: number,
  usPriority: number,
) {
  if (cardinality === "many") return "Bi-weekly + Semi-monthly";
  if (californiaPriority === usPriority) return "Conflict";
  return californiaPriority > usPriority ? "Bi-weekly" : "Semi-monthly";
}

export function resolveEffectiveDateOutcome(
  versionOneEnd: string,
  versionTwoStart: string,
  evaluationDate: string,
) {
  if (versionOneEnd >= versionTwoStart) return "Invalid overlap";
  if (evaluationDate >= "2026-09-01" && evaluationDate <= versionOneEnd)
    return "Bi-weekly (version 1)";
  if (evaluationDate >= versionTwoStart) return "Weekly (version 2)";
  return "No policy result (gap)";
}
