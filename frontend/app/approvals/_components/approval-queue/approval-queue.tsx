"use client";

import { Check, CircleAlert, Play, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Panel, PanelBody } from "@/components/ui";
import type { ChangeApprovalRequest } from "@/lib/types";
import styles from "./approval-queue.module.css";

export function ApprovalQueue({ initialRequests }: { initialRequests: ChangeApprovalRequest[] }) {
  const [requests, setRequests] = useState(initialRequests);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function decide(request: ChangeApprovalRequest, action: "approve" | "reject" | "execute") {
    setBusyId(request.id);
    setError("");
    try {
      const endpoint =
        action === "execute"
          ? "/api/backend/change-executions"
          : `/api/backend/approval-requests/${request.id}/${action}`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body:
          action === "execute" ? JSON.stringify({ approval_request_id: request.id }) : undefined,
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          result.error?.message ?? result.detail ?? `Unable to ${action} this request.`,
        );
      if (action === "execute" && typeof result.executed_at !== "string")
        throw new Error("The backend did not return the execution timestamp.");
      setRequests((current) =>
        current.map((item) =>
          item.id === request.id
            ? action === "execute"
              ? {
                  ...item,
                  status: "executed",
                  can_execute: false,
                  executed_at: result.executed_at,
                }
              : result
            : item,
        ),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : `Unable to ${action} this request.`);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="section-stack">
      {error && (
        <div className="error-banner">
          <CircleAlert size={14} />
          {error}
        </div>
      )}
      {requests.map((request) => (
        <Panel key={request.id}>
          <div className="panel-header">
            <div>
              <h2 className="panel-title">{labelFor(request.change_type)}</h2>
              <span className="secondary-cell">
                Requested by {request.requested_by} · {formatTimestamp(request.created_at)}
              </span>
            </div>
            <Badge
              tone={
                request.status === "approved" || request.status === "executed"
                  ? "success"
                  : request.status === "pending"
                    ? "accent"
                    : "neutral"
              }
            >
              {request.status}
            </Badge>
          </div>
          <PanelBody>
            <div className="field-grid">
              <div>
                <span className="field-label">Assignment impact</span>
                <span className="primary-cell">
                  {request.preview.affected_employee_count ?? 0} employees
                </span>
              </div>
              <div>
                <span className="field-label">Expires</span>
                <span className="primary-cell">{formatTimestamp(request.expires_at)}</span>
              </div>
              <div>
                <span className="field-label">Request ID</span>
                <span className="secondary-cell">{request.id}</span>
              </div>
            </div>
            <details className={styles.details}>
              <summary className="text-button">View exact proposed change</summary>
              <div className={`audit-payload ${styles.payload}`}>
                <div>
                  <span className="label">Change payload</span>
                  <pre>{JSON.stringify(request.change, null, 2)}</pre>
                </div>
              </div>
            </details>
            {request.approved_by && (
              <p className={`form-hint ${styles.approvalNote}`}>
                Approved by {request.approved_by}
                {request.approved_at ? ` on ${formatTimestamp(request.approved_at)}` : ""}. The
                approving user must execute it.
              </p>
            )}
          </PanelBody>
          {(request.can_approve || request.can_reject || request.can_execute) && (
            <div className="form-footer">
              <span className="form-hint">
                Review the previewed assignment impact before deciding.
              </span>
              <div className="heading-actions">
                {request.can_reject && (
                  <Button
                    variant="secondary"
                    disabled={busyId === request.id}
                    onClick={() => decide(request, "reject")}
                  >
                    <X size={14} />
                    Reject
                  </Button>
                )}
                {request.can_approve && (
                  <Button
                    disabled={busyId === request.id}
                    onClick={() => decide(request, "approve")}
                  >
                    <Check size={14} />
                    {busyId === request.id ? "Working…" : "Approve"}
                  </Button>
                )}
                {request.can_execute && (
                  <Button
                    disabled={busyId === request.id}
                    onClick={() => decide(request, "execute")}
                  >
                    <Play size={14} />
                    {busyId === request.id ? "Executing…" : "Execute approved change"}
                  </Button>
                )}
              </div>
            </div>
          )}
        </Panel>
      ))}
      {requests.length === 0 && (
        <div className="empty-state panel">
          <div className="empty-icon">
            <ShieldCheck size={18} />
          </div>
          <strong>No approval requests</strong>
          <span>New human-authored change previews will appear here.</span>
        </div>
      )}
    </div>
  );
}

function labelFor(changeType: string) {
  return changeType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}
