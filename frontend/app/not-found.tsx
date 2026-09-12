import { ArrowLeft, SearchX } from "lucide-react";
import { ButtonLink, Panel } from "@/components/ui";
import styles from "./status-page.module.css";

export default function NotFound() {
  return (
    <Panel className={`${styles.card} ${styles.narrow}`}>
      <div className={`preview-empty-icon ${styles.icon}`}>
        <SearchX size={20} />
      </div>
      <h1 className={styles.title}>We couldn’t find that record</h1>
      <p className={`page-subtitle ${styles.copy}`}>
        It may have been removed, or the link may be outdated.
      </p>
      <ButtonLink href="/dashboard" variant="secondary">
        <ArrowLeft size={14} /> Back to overview
      </ButtonLink>
    </Panel>
  );
}
