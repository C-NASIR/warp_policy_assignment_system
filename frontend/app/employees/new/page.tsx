import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { EmployeeEditor } from "@/components/employee-form";
import { apiConfigured, getAssignmentFields, getEmployees } from "@/lib/backend";

export const metadata: Metadata = { title: "Add employee" };

export default async function NewEmployeePage() {
  const [employees, fields] = await Promise.all([getEmployees(), getAssignmentFields()]);
  return <><div className="breadcrumb"><Link href="/employees">Employees</Link><ChevronRight size={11} /><span>Add employee</span></div><div className="page-heading"><div><p className="eyebrow">Onboarding</p><h1>Add an employee</h1><p className="page-subtitle">Enter employment facts, preview every matching assignment, then confirm when the result looks right.</p></div><span className="badge accent">Preview required</span></div><EmployeeEditor employees={employees} fields={fields} apiConfigured={apiConfigured} /></>;
}
