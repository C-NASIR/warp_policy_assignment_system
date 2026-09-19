import { CheckCircle2 } from "lucide-react";
import Link from "next/link";

const defaultPoints = [
  "Preview changes before they affect employees",
  "Resolve overlap through explicit priority",
  "Keep the decision trail with every assignment",
];

export function AuthFrame({
  children,
  eyebrow,
  title,
  titleId,
  description,
  icon,
  contextLabel = "Governed by design",
  contextTitle = "Every assignment keeps its reason.",
  contextBody = "PolicyOS turns workforce facts into explainable assignments, with change previews and an auditable record built into the workflow.",
  contextPoints = defaultPoints,
  brandDetail = "Assignment engine",
}: {
  children: React.ReactNode;
  eyebrow: string;
  title: React.ReactNode;
  titleId: string;
  description: React.ReactNode;
  icon?: React.ReactNode;
  contextLabel?: string;
  contextTitle?: string;
  contextBody?: string;
  contextPoints?: string[];
  brandDetail?: string;
}) {
  return (
    <main className="auth-page">
      <aside className="auth-context" aria-label="About PolicyOS">
        <Link href="/" className="auth-context-brand" aria-label="PolicyOS home">
          <span className="brand-mark">P</span>
          <span>PolicyOS</span>
        </Link>
        <div className="auth-context-copy">
          <p className="auth-context-label"># {contextLabel}</p>
          <h2>{contextTitle}</h2>
          <p>{contextBody}</p>
          <ul>
            {contextPoints.map((point) => (
              <li key={point}>
                <CheckCircle2 size={14} /> {point}
              </li>
            ))}
          </ul>
        </div>
        <div className="auth-context-footer">
          <span>PolicyOS / secure entry</span>
          <Link href="/learn">Learn the system</Link>
        </div>
      </aside>
      <section className="auth-stage">
        <section className="auth-card" aria-labelledby={titleId}>
          <Link href="/" className="auth-brand" aria-label="PolicyOS home">
            <span className="brand-mark">P</span>
            <span>
              <strong>PolicyOS</strong>
              <small>{brandDetail}</small>
            </span>
          </Link>
          {icon ? <div className="auth-icon">{icon}</div> : null}
          <p className="eyebrow">{eyebrow}</p>
          <h1 id={titleId}>{title}</h1>
          <p className="page-subtitle">{description}</p>
          {children}
        </section>
      </section>
    </main>
  );
}
