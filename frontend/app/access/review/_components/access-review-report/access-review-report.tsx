import { AlertCircle, AlertTriangle, CheckCircle2, Info, ShieldAlert } from "lucide-react";
import { Badge, ButtonLink, Panel, PanelBody, PanelHeader } from "@/components/ui";
import type { AccessReview } from "@/lib/types";

export function AccessReviewReport({ report }: { report: AccessReview }) {
  const severityOrder = { critical: 0, warning: 1, info: 2 } as const;
  const findings = [...report.findings].sort(
    (left, right) => severityOrder[left.severity] - severityOrder[right.severity],
  );
  const counts = {
    critical: findings.filter((finding) => finding.severity === "critical").length,
    warning: findings.filter((finding) => finding.severity === "warning").length,
    info: findings.filter((finding) => finding.severity === "info").length,
  };
  const cards = [
    ["Active users", report.active_user_count],
    ["Privileged users", report.privileged_user_count],
    ["Privileged without MFA", report.privileged_users_without_mfa],
    ["Unused roles", report.unused_role_count],
  ];
  return (
    <>
      <div className="stat-grid">
        {cards.map(([label, value]) => (
          <div className="stat-card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="review-severity-summary" aria-label="Finding severity summary">
        <Badge tone={counts.critical ? "danger" : "neutral"}>{counts.critical} critical</Badge>
        <Badge tone={counts.warning ? "warning" : "neutral"}>{counts.warning} warnings</Badge>
        <Badge tone="neutral">{counts.info} informational</Badge>
      </div>
      <Panel>
        <PanelHeader
          title="Review findings"
          caption={
            <>
              Generated {new Date(report.generated_at).toLocaleString()} across {report.role_count}{" "}
              roles.
            </>
          }
          action={
            <Badge tone={report.privileged_users_without_mfa ? "warning" : "success"}>
              {report.privileged_users_without_mfa ? (
                <ShieldAlert size={12} />
              ) : (
                <CheckCircle2 size={12} />
              )}
              {report.findings.length} findings
            </Badge>
          }
        />
        <PanelBody>
          {report.findings.length === 0 ? (
            <div className="success-banner">
              <CheckCircle2 size={14} />
              No review findings.
            </div>
          ) : (
            <div className="review-findings">
              {findings.map((finding) => {
                const FindingIcon =
                  finding.severity === "critical"
                    ? AlertCircle
                    : finding.severity === "warning"
                      ? AlertTriangle
                      : Info;
                const href = `/access?tab=${finding.subject_type === "user" ? "users" : "roles"}&search=${encodeURIComponent(finding.subject_name)}`;
                return (
                  <div
                    className={`review-finding ${finding.severity}`}
                    key={`${finding.subject_type}-${finding.subject_id}-${finding.code}`}
                  >
                    <strong>
                      <FindingIcon size={13} />
                      {finding.subject_name}
                    </strong>
                    <span className="review-finding-copy">
                      <small>{finding.message}</small>
                      <code>{finding.code.replaceAll("_", " ")}</code>
                    </span>
                    <span className="review-finding-actions">
                      <Badge
                        tone={
                          finding.severity === "critical"
                            ? "danger"
                            : finding.severity === "warning"
                              ? "warning"
                              : "neutral"
                        }
                      >
                        {finding.severity}
                      </Badge>
                      <ButtonLink href={href} variant="secondary" size="small">
                        Review {finding.subject_type}
                      </ButtonLink>
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </PanelBody>
      </Panel>
    </>
  );
}
