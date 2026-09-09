"use client";

import { CircleAlert, RotateCcw } from "lucide-react";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div
      className="panel"
      style={{ maxWidth: 540, margin: "80px auto", padding: 38, textAlign: "center" }}
    >
      <div
        className="preview-empty-icon"
        style={{ background: "var(--danger-soft)", color: "var(--danger)" }}
      >
        <CircleAlert size={20} />
      </div>
      <h1 style={{ fontSize: 22 }}>This view couldn’t be loaded</h1>
      <p className="page-subtitle" style={{ margin: "0 auto 20px" }}>
        Check that the policy API is available, then try again.
      </p>
      <button className="button" onClick={reset}>
        <RotateCcw size={14} /> Try again
      </button>
    </div>
  );
}
