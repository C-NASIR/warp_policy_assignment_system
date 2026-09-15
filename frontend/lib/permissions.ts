import type { CurrentUser } from "./types";

export function hasPermission(user: CurrentUser | null, permission: string): boolean {
  return Boolean(user && (user.permissions.includes("*") || user.permissions.includes(permission)));
}

export function firstAllowedPath(user: CurrentUser): string {
  if (user.password_change_required) return "/account/security";
  const privileged =
    user.is_root ||
    ["access:manage", "api_credentials:manage"].some(
      (permission) => hasPermission(user, permission),
    );
  if (privileged && !user.mfa_enabled) return "/account/security";
  if (user.permissions.includes("*")) return "/dashboard";
  const destinations: [string, string][] = [
    ["employees:read", "/employees"],
    ["policies:read", "/policies"],
    ["groups:read", "/groups"],
    ["audit:read", "/audit"],
    ["settings:read", "/settings"],
    ["access:read", "/access"],
  ];
  return (
    destinations.find(([permission]) => hasPermission(user, permission))?.[1] ?? "/account/security"
  );
}
