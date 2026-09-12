import type { Metadata } from "next";
import { Plus } from "lucide-react";
import { PolicyDirectory } from "./_components/policy-directory/policy-directory";
import { ButtonLink } from "@/components/ui";
import { getCurrentUser, getPolicyImpact, getPolicyPage } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";
import type { PolicyImpact } from "@/lib/types";

export const metadata: Metadata = { title: "Policies" };

const pageSize = 50;

export default async function PoliciesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const search = value(params.search);
  const status = value(params.status) || "active";
  const offset = nonnegativeInteger(value(params.offset));
  const [page, user] = await Promise.all([
    getPolicyPage({
      search,
      status: status === "all" ? undefined : status,
      limit: pageSize,
      offset,
    }),
    getCurrentUser(),
  ]);
  const impactRows = await Promise.all(
    page.items.map(async (policy) => [policy.id, await getPolicyImpact(policy.id)] as const),
  );
  const impacts = Object.fromEntries(impactRows) as Record<number, PolicyImpact | null>;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Assignment rules</p>
          <h1>Policies</h1>
          <p className="page-subtitle">
            Define who receives what, resolve overlapping rules with priority, and understand every
            policy’s reach.
          </p>
        </div>
        {hasPermission(user, "policies:create") && (
          <ButtonLink href="/policies/new">
            <Plus size={15} /> Create policy
          </ButtonLink>
        )}
      </div>
      <PolicyDirectory
        policies={page.items}
        impacts={impacts}
        total={page.total}
        limit={page.limit}
        offset={page.offset}
        filters={{ search, status }}
      />
    </>
  );
}

function value(input: string | string[] | undefined): string {
  return typeof input === "string" ? input : "";
}

function nonnegativeInteger(input: string): number {
  const parsed = Number(input);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}
