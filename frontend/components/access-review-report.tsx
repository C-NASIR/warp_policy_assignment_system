import { AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";
import type { AccessReview } from "@/lib/types";

export function AccessReviewReport({ report }: { report: AccessReview }) {
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
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Review findings</h2>
            <div className="panel-caption">
              Generated {new Date(report.generated_at).toLocaleString()} across {report.role_count}{" "}
              roles.
            </div>
          </div>
          <span className={`badge ${report.privileged_users_without_mfa ? "warning" : "success"}`}>
            {report.privileged_users_without_mfa ? (
              <ShieldAlert size={12} />
            ) : (
              <CheckCircle2 size={12} />
            )}
            {report.findings.length} findings
          </span>
        </div>
        <div className="panel-body">
          {report.findings.length === 0 ? (
            <div className="success-banner">
              <CheckCircle2 size={14} />
              No review findings.
            </div>
          ) : (
            <div className="review-findings">
              {report.findings.map((finding) => (
                <div
                  className="review-finding"
                  key={`${finding.subject_type}-${finding.subject_id}-${finding.code}`}
                >
                  <strong>
                    <AlertTriangle size={13} />
                    {finding.subject_name}
                  </strong>
                  <small>{finding.message}</small>
                  <span
                    className={`badge ${finding.severity === "critical" ? "danger" : finding.severity === "warning" ? "warning" : "neutral"}`}
                  >
                    {finding.severity} · {finding.code.replaceAll("_", " ")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </>
  );
}
