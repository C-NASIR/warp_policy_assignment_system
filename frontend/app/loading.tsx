export default function Loading() {
  return <div aria-label="Loading" style={{ display: "grid", gap: 14 }}><div style={{ width: 180, height: 28, borderRadius: 8, background: "#e8e8e2" }} /><div className="metric-grid">{Array.from({ length: 4 }).map((_, index) => <div className="metric-card" key={index} style={{ background: "#eeeeea", minHeight: 142 }} />)}</div></div>;
}
