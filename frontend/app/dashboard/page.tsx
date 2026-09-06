import Link from "next/link";
import { ArrowRight, BookOpenCheck, CircleCheckBig, Network, Plus, ShieldCheck, UserPlus, Users } from "lucide-react";
import { getAssignmentSummary, getAuditLogs, getCurrentUser, getPolicies } from "@/lib/backend";
import { titleCase } from "@/lib/format";

export default async function OverviewPage() {
  const [summary, policies, auditLogs, user] = await Promise.all([getAssignmentSummary(), getPolicies(), getAuditLogs(), getCurrentUser()]);
  const activity = [...auditLogs].sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime()).slice(0, 4).map((event) => ({ id: event.id, title: titleCase(event.entity_type), copy: `${titleCase(event.action)} by ${event.actor}`, time: relativeTime(event.timestamp) }));
  const today = new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric" }).format(new Date());
  const coverage = summary.fields.slice(0, 4).map((item) => ({ name: item.assignment_field_definition.name, caption: `${item.assigned_employee_count} of ${summary.employee_count} employees`, value: summary.employee_count ? Math.round((item.assigned_employee_count / summary.employee_count) * 100) : 0 }));
  const metrics = [
    { label: "Employees", value: summary.employee_count.toLocaleString(), delta: `${summary.employees_with_assignments} covered`, icon: Users },
    { label: "Active policies", value: policies.filter((item) => item.status === "active").length.toLocaleString(), delta: `${policies.filter((item) => item.status === "archived").length} archived`, icon: BookOpenCheck },
    { label: "Current assignments", value: summary.assignment_count.toLocaleString(), delta: `${summary.employee_count ? Math.round(summary.employees_with_assignments / summary.employee_count * 100) : 0}% covered`, icon: CircleCheckBig },
    { label: "Manual overrides", value: summary.override_assignment_count.toLocaleString(), delta: `${summary.policy_assignment_count.toLocaleString()} policy-derived`, icon: ShieldCheck },
  ];
  return (
    <>
      <div className="page-heading">
        <div><p className="eyebrow">{today}</p><h1>Good morning, {user?.name.split(" ")[0] ?? "Priya"}</h1><p className="page-subtitle">Your policy assignments are healthy. Three future changes are scheduled and no conflicts need attention.</p></div>
        <Link className="button" href="/policies/new"><Plus size={15} /> Create policy</Link>
      </div>
      <section className="metric-grid" aria-label="Assignment system metrics">
        {metrics.map((metric) => { const Icon = metric.icon; return (
          <article className="metric-card" key={metric.label}>
            <div className="metric-icon"><Icon size={16} strokeWidth={1.8} /></div><div className="metric-delta">{metric.delta}</div>
            <div className="metric-value">{metric.value}</div><div className="metric-label">{metric.label}</div>
          </article>
        ); })}
      </section>
      <section className="dashboard-grid">
        <article className="panel">
          <div className="panel-header"><h2 className="panel-title">Assignment coverage</h2><Link className="panel-link" href="/employees">View employees <ArrowRight size={13} /></Link></div>
          <div className="coverage-list">{coverage.map((item) => (
            <div className="coverage-row" key={item.name}>
              <div><div className="coverage-name">{item.name}</div><div className="coverage-caption">{item.caption}</div></div>
              <div className="progress-track" aria-label={`${item.value}% covered`}><div className="progress-bar" style={{ width: `${item.value}%` }} /></div>
              <div className="coverage-value">{item.value}%</div>
            </div>
          ))}</div>
        </article>
        <article className="panel">
          <div className="panel-header"><h2 className="panel-title">Recent changes</h2><Link className="panel-link" href="/audit">Audit log <ArrowRight size={13} /></Link></div>
          <div className="activity-list">{activity.map((item) => (
            <div className="activity-item" key={item.id}><div className="activity-icon"><CircleCheckBig size={13} /></div><div><div className="activity-copy"><strong>{item.title}</strong> {item.copy}</div><div className="activity-time">{item.time}</div></div></div>
          ))}{activity.length === 0 && <div className="empty-state compact">No changes have been recorded yet.</div>}</div>
        </article>
      </section>
      <section className="quick-actions" aria-label="Quick actions">
        <Link className="quick-action" href="/employees/new"><span className="quick-action-icon"><UserPlus size={16} /></span><span><span className="quick-action-title">Onboard an employee</span><span className="quick-action-caption">Preview assignments before saving</span></span></Link>
        <Link className="quick-action" href="/policies/new"><span className="quick-action-icon"><BookOpenCheck size={16} /></span><span><span className="quick-action-title">Define a policy</span><span className="quick-action-caption">Build rules with guided conditions</span></span></Link>
        <Link className="quick-action" href="/groups"><span className="quick-action-icon"><Network size={16} /></span><span><span className="quick-action-title">Review a group</span><span className="quick-action-caption">See inherited policy coverage</span></span></Link>
      </section>
    </>
  );
}

function relativeTime(timestamp: string) {
  const elapsedMinutes = Math.max(0, Math.round((Date.now() - new Date(timestamp).getTime()) / 60_000));
  if (elapsedMinutes < 1) return "Just now";
  if (elapsedMinutes < 60) return `${elapsedMinutes}m ago`;
  const hours = Math.round(elapsedMinutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}
