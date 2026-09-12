import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { redirect } from "next/navigation";
import { EmployeeEditor } from "../_components/employee-editor/employee-editor";
import { Badge } from "@/components/ui";
import {
  getAssignmentFields,
  getCurrentUser,
  getEmployeeReferenceData,
  getEmployees,
} from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Add employee" };

export default async function NewEmployeePage() {
  const user = await getCurrentUser();
  if (!hasPermission(user, "employees:create")) redirect("/forbidden");
  const [employees, fields, referenceData] = await Promise.all([
    getEmployees(),
    getAssignmentFields(),
    getEmployeeReferenceData(),
  ]);
  return (
    <>
      <Link className="page-back-link" href="/employees">
        <ArrowLeft size={13} />
        Back to employees
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Onboarding</p>
          <h1>Add an employee</h1>
          <p className="page-subtitle">
            Enter employment facts, preview every matching assignment, then confirm when the result
            looks right.
          </p>
        </div>
        <Badge tone="accent">Preview required</Badge>
      </div>
      <EmployeeEditor employees={employees} fields={fields} referenceData={referenceData} />
    </>
  );
}
