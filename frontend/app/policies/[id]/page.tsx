import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight, CircleCheckBig, Info, Pencil, Users } from "lucide-react";
import { notFound } from "next/navigation";
import { PolicyLifecycle } from "@/components/features/policies";
import { Badge, ButtonLink, Panel, PanelBody, PanelHeader } from "@/components/ui";
import { getAssignmentFields, getCurrentUser, getPolicy, getPolicyImpact } from "@/lib/backend";
import { formatDate, titleCase } from "@/lib/format";
import { hasPermission } from "@/lib/permissions";
import type { ConditionGroup } from "@/lib/types";
import styles from "./policy-detail.module.css";

export async function generateMetadata({ params }: PageProps<"/policies/[id]">): Promise<Metadata> {
  const { id } = await params;
  const policy = await getPolicy(Number(id));
  return {
    title: policy?.name ?? "Policy",
    description: policy ? `Assignment rule and impact for ${policy.name}` : "Policy details",
    openGraph: { images: [] },
    twitter: { images: [] },
  };
}

export default async function PolicyDetailPage({ params }: PageProps<"/policies/[id]">) {
  const { id } = await params;
  const user = await getCurrentUser();
  const [policy, impact, fields] = await Promise.all([
    getPolicy(Number(id)),
    getPolicyImpact(Number(id)),
    hasPermission(user, "settings:read") ? getAssignmentFields() : [],
  ]);
  if (!policy) notFound();
  const current = policy.versions.at(-1);
  const assignmentValueCount = current?.values.length ?? 0;
  const fieldNames = Object.fromEntries(fields.map((field) => [field.id, field.name]));
  return (
    <>
      <Link className="page-back-link" href="/policies">
        <ArrowLeft size={13} />
        Back to policies
      </Link>
      <div className="detail-hero">
        <div>
          <div className={`heading-actions ${styles.versionBadge}`}>
            <Badge>Version {current?.version_number ?? "—"}</Badge>
          </div>
          <h1 className="detail-title">{policy.name}</h1>
          <div className="detail-meta">
            Effective {formatDate(current?.effective_from)} · Priority {current?.priority ?? "—"}
          </div>
        </div>
        <div className="heading-actions">
          <PolicyLifecycle policy={policy} />
          {policy.capabilities.can_create_version && (
            <ButtonLink variant="secondary" href={`/policies/new?policyId=${policy.id}`}>
              <Pencil size={14} /> New version
            </ButtonLink>
          )}
        </div>
      </div>
      <div className="detail-grid">
        <div className="section-stack">
          <Panel>
            <PanelHeader
              title="Who this applies to"
              action={
                <Badge tone="accent">
                  {current?.condition_group.logical_operator === "or"
                    ? "Any condition"
                    : "All conditions"}
                </Badge>
              }
            />
            <PanelBody>
              {current ? (
                <RuleSummary group={current.condition_group} />
              ) : (
                <div className="empty-state compact">No active rule version.</div>
              )}
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader
              title="Assignments provided"
              action={
                <Badge>
                  {assignmentValueCount} {assignmentValueCount === 1 ? "value" : "values"}
                </Badge>
              }
            />
            <PanelBody>
              <div className="assignment-list">
                {current?.values.map((value, index) => (
                  <div
                    className="assignment-card"
                    key={`${value.assignment_field_definition_id}-${value.value}-${index}`}
                  >
                    <div className="assignment-summary policy-assignment-summary">
                      <span>
                        <span className="assignment-field">
                          {fieldNames[value.assignment_field_definition_id] ??
                            `Field ${value.assignment_field_definition_id}`}
                        </span>
                        <span className="assignment-value">{value.value}</span>
                      </span>
                      <span className="assignment-source">
                        <strong>This policy</strong>Priority {current.priority}
                      </span>
                      <span
                        className="policy-assignment-status"
                        aria-label="Provided by this policy"
                      >
                        <CircleCheckBig size={15} aria-hidden="true" />
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </PanelBody>
          </Panel>
          <Panel>
            <PanelHeader title="Version history" />
            <PanelBody>
              <div className="version-timeline">
                {[...policy.versions].reverse().map((version) => (
                  <div className="version-row" key={version.id}>
                    <div className="version-dot" />
                    <div>
                      <div className="version-title">
                        Version {version.version_number} · Priority {version.priority}
                      </div>
                      <div className="version-caption">
                        Effective {formatDate(version.effective_from)} · Created by{" "}
                        {version.created_by ?? "System"}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </PanelBody>
          </Panel>
        </div>
        <aside className="section-stack">
          <Panel>
            <div className="impact-hero">
              <Users size={17} />
              <div className="impact-number">{impact?.selected_employee_count ?? 0}</div>
              <div className="impact-label">employees receive assignments from this policy</div>
            </div>
            <PanelBody>
              <div className="side-stat">
                <div className="side-stat-value">{impact?.matched_employee_count ?? 0}</div>
                <div className="side-stat-label">Employees match the rule</div>
              </div>
              <div className="side-stat">
                <div className="side-stat-value">{impact?.selected_assignment_count ?? 0}</div>
                <div className="side-stat-label">Selected assignment values</div>
              </div>
              <div className="side-stat">
                <div className="side-stat-value">
                  {impact?.matched_without_selected_assignment_count ?? 0}
                </div>
                <div className="side-stat-label">Matched but another policy won</div>
              </div>
            </PanelBody>
          </Panel>
          <div className="callout">
            <Info size={15} />
            <span>
              Matching means the rule applies. Selected means this policy actually supplies the
              final assignment after priority and overrides.
            </span>
          </div>
          <Link className="quick-action" href="/employees">
            <span className="quick-action-icon">
              <Users size={16} />
            </span>
            <span>
              <span className="quick-action-title">Explore affected employees</span>
              <span className="quick-action-caption">Review assignment sources and evidence</span>
            </span>
            <ArrowRight className={styles.actionArrow} size={14} />
          </Link>
        </aside>
      </div>
    </>
  );
}

function RuleSummary({ group, nested = false }: { group: ConditionGroup; nested?: boolean }) {
  const operands = [
    ...group.conditions.map((condition, index) => (
      <span className="rule-expression" key={`condition-${condition.field}-${index}`}>
        <span className="rule-token">{titleCase(condition.field)}</span>
        <strong>{condition.operator}</strong>
        <span className="rule-token">{condition.value}</span>
      </span>
    )),
    ...group.child_groups.map((child, index) => (
      <RuleSummary group={child} nested key={`group-${index}`} />
    )),
  ];
  return (
    <div className={`rule-summary${nested ? " nested" : ""}`}>
      <div className="rule-summary-label">
        {nested ? "Nested group" : "Employees where"}{" "}
        <strong>{group.logical_operator === "and" ? "all" : "any"}</strong> of these match
      </div>
      <div className="rule-summary-items">
        {operands.map((operand, index) => (
          <div className="rule-summary-row" key={index}>
            {index > 0 && (
              <span className="logic-pill">{group.logical_operator.toUpperCase()}</span>
            )}
            {operand}
          </div>
        ))}
      </div>
    </div>
  );
}
