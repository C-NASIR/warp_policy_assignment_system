export function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export function formatEmployeeId(id: number) {
  return `#${String(id).padStart(4, "0")}`;
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "Ongoing";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

export function titleCase(value: string) {
  return value
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function formatStateValue(
  value: unknown,
  states: { code: string; label: string }[],
) {
  const text = String(value ?? "");
  return states.find((option) => option.code === text)?.label ?? text;
}
