import Link from "next/link";
import { ArrowLeft, SearchX } from "lucide-react";

export default function NotFound() {
  return (
    <div
      className="panel"
      style={{ maxWidth: 520, margin: "80px auto", padding: 38, textAlign: "center" }}
    >
      <div className="preview-empty-icon">
        <SearchX size={20} />
      </div>
      <h1 style={{ fontSize: 22 }}>We couldn’t find that record</h1>
      <p className="page-subtitle" style={{ margin: "0 auto 20px" }}>
        It may have been removed, or the link may be outdated.
      </p>
      <Link className="button secondary" href="/dashboard">
        <ArrowLeft size={14} /> Back to overview
      </Link>
    </div>
  );
}
