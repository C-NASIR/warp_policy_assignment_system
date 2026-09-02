"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

type ToolDefinition = {
  name: string;
  title: string;
  description: string;
  inputSchema: Record<string, unknown>;
  annotations: { readOnlyHint: boolean; untrustedContentHint: boolean };
  execute(input: unknown): Promise<Record<string, unknown>>;
};

declare global {
  interface Document {
    modelContext?: {
      registerTool(tool: ToolDefinition, options?: { signal?: AbortSignal }): void | Promise<void>;
    };
  }
}

export function WebMcpTools() {
  const router = useRouter();

  useEffect(() => {
    const context = document.modelContext;
    if (!context?.registerTool) return;
    const lifecycle = new AbortController();
    const tools: ToolDefinition[] = [
      {
        name: "start_employee_onboarding",
        title: "Start employee onboarding",
        description: "Open the employee onboarding flow so employment facts can be entered and assignments previewed before saving.",
        inputSchema: { type: "object", properties: {}, additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: false },
        async execute() {
          router.push("/employees/new");
          return { status: "opened", route: "/employees/new" };
        },
      },
      {
        name: "start_policy_creation",
        title: "Start policy creation",
        description: "Open the policy builder to define employee conditions, assignment values, priority, and effective dates.",
        inputSchema: { type: "object", properties: {}, additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: false },
        async execute() {
          router.push("/policies/new");
          return { status: "opened", route: "/policies/new" };
        },
      },
      {
        name: "open_employee_assignments",
        title: "Open employee assignments",
        description: "Open an employee detail page to inspect their resolved assignments and policy explanations.",
        inputSchema: { type: "object", properties: { employeeId: { type: "integer", minimum: 1 } }, required: ["employeeId"], additionalProperties: false },
        annotations: { readOnlyHint: true, untrustedContentHint: false },
        async execute(input) {
          const employeeId = typeof input === "object" && input !== null && "employeeId" in input ? Number(input.employeeId) : Number.NaN;
          if (!Number.isInteger(employeeId) || employeeId < 1) throw new Error("employeeId must be a positive integer");
          const route = `/employees/${employeeId}`;
          router.push(route);
          return { status: "opened", route, employeeId };
        },
      },
    ];

    for (const tool of tools) {
      try {
        void Promise.resolve(context.registerTool(tool, { signal: lifecycle.signal })).catch(() => undefined);
      } catch {
        // WebMCP is progressive enhancement; the visible interface remains complete.
      }
    }
    return () => lifecycle.abort();
  }, [router]);

  return null;
}
