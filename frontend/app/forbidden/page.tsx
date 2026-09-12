import { ShieldX } from "lucide-react";
import { ButtonLink } from "@/components/ui";
import { getCurrentUser } from "@/lib/backend";
import { firstAllowedPath } from "@/lib/permissions";
import styles from "./forbidden.module.css";

export default async function ForbiddenPage() {
  const user = await getCurrentUser();
  const destination = user ? firstAllowedPath(user) : "/login";
  return (
    <section className="access-denied">
      <div className="confirm-icon">
        <ShieldX size={19} />
      </div>
      <p className="eyebrow">Access restricted</p>
      <h1>You do not have permission to view this page</h1>
      <p className="page-subtitle">
        Your assigned roles determine which PolicyOS areas and actions are available. Ask an access
        administrator if you believe this is incorrect.
      </p>
      <ButtonLink className={styles.action} href={destination}>
        Go to an available page
      </ButtonLink>
    </section>
  );
}
