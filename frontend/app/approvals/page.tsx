import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { ApprovalQueue } from "@/components/features/approvals";
import { Badge } from "@/components/ui";
import { getApprovalRequests, getCurrentUser } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";

export const metadata: Metadata = { title: "Approvals" };

export default async function ApprovalsPage() {
  const user = await getCurrentUser();
  if (!hasPermission(user, "changes:approve")) redirect("/forbidden");
  const requests = await getApprovalRequests();
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Separation of duties</p>
          <h1>Change approvals</h1>
          <p className="page-subtitle">
            Review sensitive changes, approve or reject another author’s request, and execute only
            what was approved.
          </p>
        </div>
        <Badge tone="accent">
          {requests.filter((request) => request.status === "pending").length} pending
        </Badge>
      </div>
      <ApprovalQueue initialRequests={requests} />
    </>
  );
}
