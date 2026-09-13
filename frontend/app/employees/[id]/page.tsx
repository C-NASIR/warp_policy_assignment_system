import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Info, Pencil, ShieldCheck } from "lucide-react";
import { notFound } from "next/navigation";
import { EmployeeEditor } from "../_components/employee-editor/employee-editor";
import { AssignmentCard } from "./_components/assignment-card/assignment-card";
import { OverrideManager } from "./_components/override-manager/override-manager";
import { Badge, Panel, PanelBody, PanelHeader } from "@/components/ui";
import {
  getAssignmentFields,
  getCurrentUser,
  getEmployee,
  getEmployeeAssignmentHistory,
  getEmployeeAssignments,
  getEmployeeReferenceData,
  getEmployeeOverrides,
  getEmployees,
} from "@/lib/backend";
import { formatDate, formatEmployeeId, initials } from "@/lib/format";
import { hasPermission } from "@/lib/permissions";
import styles from "./employee-detail.module.css";

export async function generateMetadata({
  params,
}: PageProps<"/employees/[id]">): Promise<Metadata> {
  const { id } = await params;
  const employee = await getEmployee(Number(id));
  return {
    title: employee?.name ?? "Employee",
    description: employee ? `Policy assignments for ${employee.name}` : "Employee details",
    openGraph: { images: [] },
    twitter: { images: [] },
  };
}

export default async function EmployeeDetailPage({ params }: PageProps<"/employees/[id]">) {
  const { id } = await params;
  const user = await getCurrentUser();
  const canReadAssignments = hasPermission(user, "assignments:read");
  const canReadSettings = hasPermission(user, "settings:read");
  const [employee, assignments, allEmployees, fields, overrides, history, referenceData] =
    await Promise.all([
      getEmployee(Number(id)),
      canReadAssignments ? getEmployeeAssignments(Number(id)) : [],
      getEmployees(),
      canReadSettings ? getAssignmentFields() : [],
      canReadAssignments ? getEmployeeOverrides(Number(id)) : [],
      canReadAssignments ? getEmployeeAssignmentHistory(Number(id)) : [],
      getEmployeeReferenceData(),
    ]);
  if (!employee) notFound();
  const manager = allEmployees.find((item) => item.id === employee.manager_id);
  const policyCount = new Set(
    assignments.map((item) => item.source_policy_version_id).filter(Boolean),
  ).size;
  const overrideCount = assignments.filter((item) => item.source_override_id).length;
  return (
    <>
      <Link className="page-back-link" href="/employees">
        <ArrowLeft size={13} />
        Back to employees
      </Link>
      <div className="detail-hero">
        <div className="detail-identity">
          <div className="detail-avatar">{initials(employee.name)}</div>
          <div>
            <h1 className="detail-title">{employee.name}</h1>
            <div className="detail-meta">
              {employee.department} · {employee.employee_type} ·{" "}
              {employee.location ?? employee.state_label}
            </div>
          </div>
        </div>
        {hasPermission(user, "employees:update") && (
          <EmployeeEditor
            employee={employee}
            employees={allEmployees}
            referenceData={referenceData}
            mfaEnabled={user?.mfa_enabled ?? false}
            trigger={
              <>
                <Pencil size={14} /> Edit employee
              </>
            }
            compact
          />
        )}
      </div>
      <div className={canReadAssignments ? "detail-grid" : "section-stack"}>
        <div className="section-stack">
          {canReadAssignments && (
            <Panel>
              <PanelHeader
                title="Current assignments"
                action={<Badge tone="success">{assignments.length} resolved</Badge>}
              />
              <PanelBody>
                {assignments.length ? (
                  <div className="assignment-list">
                    {assignments.map((item) => (
                      <AssignmentCard
                        assignment={item}
                        states={referenceData.states}
                        key={item.id}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty-state">No active assignments.</div>
                )}
              </PanelBody>
            </Panel>
          )}
          <Panel>
            <PanelHeader title="Employee profile" />
            <PanelBody>
              <div className="profile-grid">
                <div>
                  <span className="label">Department</span>
                  <div className="profile-value">{employee.department}</div>
                </div>
                <div>
                  <span className="label">Employment type</span>
                  <div className="profile-value">{employee.employee_type}</div>
                </div>
                <div>
                  <span className="label">Work location</span>
                  <div className="profile-value">{employee.location ?? "Not set"}</div>
                  <div className="profile-caption">{employee.state_label}</div>
                </div>
                <div>
                  <span className="label">Start date</span>
                  <div className="profile-value">{formatDate(employee.start_date)}</div>
                </div>
                <div>
                  <span className="label">Manager</span>
                  <div className="profile-value">{manager?.name ?? "No manager"}</div>
                </div>
                <div>
                  <span className="label">Employee ID</span>
                  <div className="profile-value">{formatEmployeeId(employee.id)}</div>
                </div>
              </div>
            </PanelBody>
          </Panel>
          {canReadAssignments && (
            <OverrideManager
              employee={employee}
              fields={fields}
              initialOverrides={overrides}
              history={history}
              canManage={hasPermission(user, "assignments:manage")}
            />
          )}
        </div>
        {canReadAssignments && (
          <aside className="section-stack">
            <Panel>
              <PanelHeader title="Assignment health" />
              <PanelBody>
                <div className="side-stat">
                  <div className="side-stat-value">{assignments.length}</div>
                  <div className="side-stat-label">Current assignment values</div>
                </div>
                <div className="side-stat">
                  <div className="side-stat-value">{policyCount}</div>
                  <div className="side-stat-label">Source policies</div>
                </div>
                <div className="side-stat">
                  <div className="side-stat-value">{overrideCount}</div>
                  <div className="side-stat-label">Manual overrides</div>
                </div>
              </PanelBody>
            </Panel>
            <div className="callout">
              <Info size={15} />
              <span>
                Open any assignment to see the exact policy, matched facts, group origin, and
                priority decision.
              </span>
            </div>
            {overrideCount > 0 && (
              <div className={`callout ${styles.warningCallout}`}>
                <ShieldCheck size={15} />
                <span>
                  This employee has {overrideCount} manual override. Review it periodically to
                  confirm it is still needed.
                </span>
              </div>
            )}
          </aside>
        )}
      </div>
    </>
  );
}
