import type { Metadata } from "next";
import { Braces } from "lucide-react";
import { getAssignmentFields } from "@/lib/backend";

export const metadata: Metadata = { title: "Assignment fields" };

export default async function SettingsPage() {
  const fields = await getAssignmentFields();
  return <><div className="page-heading"><div><p className="eyebrow">System setup</p><h1>Assignment fields</h1><p className="page-subtitle">Define the categories policies can assign and whether each accepts one or many values.</p></div><span className="badge">Catalog</span></div><div className="data-panel"><table className="data-table"><thead><tr><th>Assignment field</th><th>Cardinality</th><th>Conflict resolution</th><th>Used for</th></tr></thead><tbody>{fields.map((field) => <tr key={field.id}><td><span className="person-cell"><span className="avatar"><Braces size={14} /></span><span className="primary-cell">{field.name}</span></span></td><td><span className="badge accent">{field.cardinality === "one" ? "One value" : "Many values"}</span></td><td>{field.cardinality === "one" ? "Highest priority wins" : "Set union"}</td><td><span className="secondary-cell" style={{ margin: 0 }}>{field.cardinality === "one" ? "Pay, leave, schedules" : "Access, benefits, training"}</span></td></tr>)}</tbody></table></div></>;
}
