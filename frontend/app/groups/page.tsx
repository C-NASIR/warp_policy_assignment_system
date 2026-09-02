import type { Metadata } from "next";
import { Network, Users } from "lucide-react";
import { getGroups } from "@/lib/backend";

export const metadata: Metadata = { title: "Groups" };

export default async function GroupsPage() {
  const groups = await getGroups();
  return <><div className="page-heading"><div><p className="eyebrow">Collections</p><h1>Groups</h1><p className="page-subtitle">Review explicit employee groups and the policies their members inherit.</p></div><span className="badge">Management arrives in Phase 2</span></div><div className="metric-grid">{groups.map((group, index) => <article className="metric-card" key={group.id}><div className="metric-icon"><Network size={16} /></div><div className="metric-value" style={{ fontSize: 16 }}>{group.name}</div><div className="metric-label">{[64, 18, 196, 27][index] ?? 0} members · {index % 2 + 1} attached policies</div><div className="metric-delta"><Users size={13} /></div></article>)}</div></>;
}
