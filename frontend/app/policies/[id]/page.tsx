import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ChevronRight, CircleCheckBig, Info, Pencil, Users } from "lucide-react";
import { notFound } from "next/navigation";
import { getAssignmentFields, getPolicy, getPolicyImpact } from "@/lib/backend";
import { formatDate, titleCase } from "@/lib/format";

export async function generateMetadata({ params }: PageProps<"/policies/[id]">): Promise<Metadata> {
  const { id } = await params; const policy = await getPolicy(Number(id));
  return { title: policy?.name ?? "Policy", description: policy ? `Assignment rule and impact for ${policy.name}` : "Policy details", openGraph: { images: [] }, twitter: { images: [] } };
}

export default async function PolicyDetailPage({ params }: PageProps<"/policies/[id]">) {
  const { id } = await params;
  const [policy, impact, fields] = await Promise.all([getPolicy(Number(id)), getPolicyImpact(Number(id)), getAssignmentFields()]);
  if (!policy) notFound();
  const current = policy.versions.at(-1);
  const fieldNames = Object.fromEntries(fields.map((field) => [field.id, field.name]));
  return <><div className="breadcrumb"><Link href="/policies">Policies</Link><ChevronRight size={11} /><span>{policy.name}</span></div>
    <div className="detail-hero"><div><div className="heading-actions" style={{ marginBottom: 7 }}><span className={`badge ${policy.status === "active" ? "success" : ""}`}>{policy.status}</span><span className="badge">Version {current?.version_number ?? "—"}</span></div><h1 className="detail-title">{policy.name}</h1><div className="detail-meta">Effective {formatDate(current?.effective_from)} · Priority {current?.priority ?? "—"}</div></div><Link className="button secondary" href={`/policies/new?policyId=${policy.id}`}><Pencil size={14} /> New version</Link></div>
    <div className="detail-grid"><div className="section-stack">
      <section className="panel"><div className="panel-header"><h2 className="panel-title">Who this applies to</h2><span className="badge accent">{current?.condition_group.logical_operator === "or" ? "Any condition" : "All conditions"}</span></div><div className="panel-body"><div className="plain-rule"><span>Employees where</span>{current?.condition_group.conditions.map((condition, index) => <span key={`${condition.field}-${index}`}><span className="rule-token">{titleCase(condition.field)}</span> <strong>{condition.operator}</strong> <span className="rule-token">{condition.value}</span>{index < current.condition_group.conditions.length - 1 && <span> {current.condition_group.logical_operator.toUpperCase()} </span>}</span>)}</div></div></section>
      <section className="panel"><div className="panel-header"><h2 className="panel-title">Assignments provided</h2><span className="badge">{current?.values.length ?? 0} values</span></div><div className="panel-body"><div className="assignment-list">{current?.values.map((value, index) => <div className="assignment-card" key={`${value.assignment_field_definition_id}-${value.value}-${index}`}><div className="assignment-summary" style={{ cursor: "default", gridTemplateColumns: "1fr 1fr auto" }}><span><span className="assignment-field">{fieldNames[value.assignment_field_definition_id] ?? `Field ${value.assignment_field_definition_id}`}</span><span className="assignment-value">{value.value}</span></span><span className="assignment-source"><strong>This policy</strong>Priority {current.priority}</span><CircleCheckBig size={15} color="var(--success)" /></div></div>)}</div></div></section>
      <section className="panel"><div className="panel-header"><h2 className="panel-title">Version history</h2></div><div className="panel-body"><div className="version-timeline">{[...policy.versions].reverse().map((version) => <div className="version-row" key={version.id}><div className="version-dot" /><div><div className="version-title">Version {version.version_number} · Priority {version.priority}</div><div className="version-caption">Effective {formatDate(version.effective_from)} · Created by {version.created_by ?? "System"}</div></div></div>)}</div></div></section>
    </div><aside className="section-stack">
      <section className="panel"><div className="impact-hero"><Users size={17} /><div className="impact-number">{impact?.selected_employee_count ?? 0}</div><div className="impact-label">employees receive assignments from this policy</div></div><div className="panel-body"><div className="side-stat"><div className="side-stat-value">{impact?.matched_employee_count ?? 0}</div><div className="side-stat-label">Employees match the rule</div></div><div className="side-stat"><div className="side-stat-value">{impact?.selected_assignment_count ?? 0}</div><div className="side-stat-label">Selected assignment values</div></div><div className="side-stat"><div className="side-stat-value">{impact?.matched_without_selected_assignment_count ?? 0}</div><div className="side-stat-label">Matched but another policy won</div></div></div></section>
      <div className="callout"><Info size={15} /><span>Matching means the rule applies. Selected means this policy actually supplies the final assignment after priority and overrides.</span></div>
      <Link className="quick-action" href="/employees"><span className="quick-action-icon"><Users size={16} /></span><span><span className="quick-action-title">Explore affected employees</span><span className="quick-action-caption">Review assignment sources and evidence</span></span><ArrowRight size={14} style={{ marginLeft: "auto" }} /></Link>
    </aside></div>
  </>;
}
