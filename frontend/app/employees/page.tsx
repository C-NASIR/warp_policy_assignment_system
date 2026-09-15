import type { Metadata } from "next";
import { Plus } from "lucide-react";
import { EmployeeDirectory } from "./_components/employee-directory/employee-directory";
import { ButtonLink } from "@/components/ui";
import { getCurrentUser, getEmployeePage, getEmployeeReferenceData } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Employees" };

const pageSize = 10;

export default async function EmployeesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const search = value(params.search);
  const state = value(params.state);
  const department = value(params.department);
  const employeeType = value(params.employee_type);
  const offset = nonnegativeInteger(value(params.offset));
  const [page, referenceData, user] = await Promise.all([
    getEmployeePage({ search, state, department, employeeType, limit: pageSize, offset }),
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
          <ButtonLink href="/employees/new">
            <Plus size={15} /> Add employee
          </ButtonLink>
        )}
      </div>
      <EmployeeDirectory
        employees={page.items}
        referenceData={referenceData}
        total={page.total}
        limit={page.limit}
        offset={page.offset}
        filters={{ search, state, department, employeeType }}
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
