import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "lucide-react";
import { EmployeeDirectory } from "@/components/employee-directory";
import { getCurrentUser, getEmployeePage, getEmployeeReferenceData } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Employees" };

const pageSize = 50;

export default async function EmployeesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const search = value(params.search);
  const department = value(params.department);
  const employeeType = value(params.employee_type);
  const offset = nonnegativeInteger(value(params.offset));
  const [page, referenceData, user] = await Promise.all([
    getEmployeePage({ search, department, employeeType, limit: pageSize, offset }),
    getEmployeeReferenceData(),
    getCurrentUser(),
  ]);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">People</p>
          <h1>Employees</h1>
          <p className="page-subtitle">
            See each employee’s policy coverage, current assignments, and downstream effects.
          </p>
        </div>
        {hasPermission(user, "employees:create") && (
          <Link className="button" href="/employees/new">
            <Plus size={15} /> Add employee
          </Link>
        )}
      </div>
      <EmployeeDirectory
        employees={page.items}
        referenceData={referenceData}
        total={page.total}
        limit={page.limit}
        offset={page.offset}
        filters={{ search, department, employeeType }}
      />
    </>
  );
}

function value(input: string | string[] | undefined): string {
  return typeof input === "string" ? input : "";
}

function nonnegativeInteger(input: string): number {
  const parsed = Number(input);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}
