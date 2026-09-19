import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { AuthFrame } from "@/components/features/auth/auth-frame/auth-frame";
import { ButtonLink } from "@/components/ui";

export function SignupForm() {
  return (
    <AuthFrame
      eyebrow="Join your workspace"
      title="Get access to PolicyOS"
      titleId="signup-title"
      description="Ask your PolicyOS administrator to create an account for you, then sign in with the credentials they provide."
      icon={<ShieldCheck size={21} />}
      contextLabel="Access follows governance"
      contextTitle="The right people get the right control."
      contextBody="PolicyOS workspaces are administrator-managed so policy authorship, employee visibility, and sensitive actions stay accountable."
    >
      <ButtonLink className="auth-submit" href="/login" fullWidth>
        Sign in
      </ButtonLink>
      <Link className="auth-switch" href="/">
        Back to home
      </Link>
    </AuthFrame>
  );
}
