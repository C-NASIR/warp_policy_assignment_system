import type { CurrentUser } from "./types";

export function hasPermission(user: CurrentUser | null, permission: string): boolean {
  return Boolean(user && (user.permissions.includes("*") || user.permissions.includes(permission)));
}

export function firstAllowedPath(user: CurrentUser): string {
  if (user.password_change_required) return "/account/security";
  if (user.permissions.includes("*")) return "/";
  const destinations: [string, string][] = [
    ["employees:read", "/employees"],
    ["policies:read", "/policies"],
    ["groups:read", "/groups"],
    ["audit:read", "/audit"],
    ["settings:read", "/settings"],
    ["access:read", "/access"],
  ];
  return destinations.find(([permission]) => hasPermission(user, permission))?.[1] ?? "/account/security";
}
