import Link from "next/link";
import { LockKeyhole, MoveUpRight } from "lucide-react";
import defaultMdxComponents from "fumadocs-ui/mdx";
import type { MDXComponents } from "mdx/types";
import { apiConfigured } from "@/lib/backend";
import { hasPermission } from "@/lib/permissions";
import type { CurrentUser } from "@/lib/types";

type PolicyLinkProps = {
  href: string;
  permission?: string;
  children: React.ReactNode;
};

function PolicyLink({ currentUser, href, permission, children }: PolicyLinkProps & { currentUser: CurrentUser | null }) {
  const allowed = !apiConfigured || !permission || hasPermission(currentUser, permission);

  if (!allowed) {
    return (
      <span className="learn-policy-link locked">
        <span><LockKeyhole size={15} /></span>
        <span><strong>{children}</strong><small>Requires {permission}</small></span>
      </span>
    );
  }

  return (
    <Link className="learn-policy-link" href={href}>
      <span><MoveUpRight size={15} /></span>
      <span><strong>{children}</strong><small>Open in PolicyOS</small></span>
    </Link>
  );
}

export function getLearnMdxComponents(currentUser: CurrentUser | null, components?: MDXComponents): MDXComponents {
  return {
    ...defaultMdxComponents,
    PolicyLink: (props: PolicyLinkProps) => <PolicyLink currentUser={currentUser} {...props} />,
    ...components,
  };
}
