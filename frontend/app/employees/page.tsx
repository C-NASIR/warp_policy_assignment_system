import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "lucide-react";
import { EmployeeDirectory } from "@/components/employee-directory";
import { getEmployees } from "@/lib/backend";

export const metadata: Metadata = { title: "Employees" };

export default async function EmployeesPage() {
  const employees = await getEmployees();
  return (
    <>
      <div className="page-heading"><div><p className="eyebrow">People</p><h1>Employees</h1><p className="page-subtitle">See each employee’s policy coverage, current assignments, and downstream effects.</p></div><Link className="button" href="/employees/new"><Plus size={15} /> Add employee</Link></div>
      <EmployeeDirectory employees={employees} />
    </>
  );
}
