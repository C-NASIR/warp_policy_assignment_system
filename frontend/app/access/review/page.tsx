import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { AccessReviewReport } from "@/components/features/access";
import { getAccessReview } from "@/lib/backend";

export const metadata: Metadata = { title: "Access review" };

export default async function AccessReviewPage() {
  const report = await getAccessReview();
  if (!report) notFound();
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Security hardening</p>
          <h1>Access review</h1>
          <p className="page-subtitle">
            Identify privileged accounts without MFA, dormant users, unused roles, and broad data
            scopes.
          </p>
        </div>
      </div>
      <AccessReviewReport report={report} />
    </>
  );
}
