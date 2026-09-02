import type { Metadata } from "next";
import { AssignmentFieldManager } from "@/components/assignment-field-manager";
import { apiConfigured, getAssignmentFields } from "@/lib/backend";

export const metadata: Metadata = { title: "Assignment fields" };

export default async function SettingsPage() {
  const fields = await getAssignmentFields();
  return <AssignmentFieldManager initialFields={fields} apiConfigured={apiConfigured} />;
}
