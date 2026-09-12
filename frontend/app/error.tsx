"use client";

import { CircleAlert, RotateCcw } from "lucide-react";
import { Button, Panel } from "@/components/ui";
import styles from "./status-page.module.css";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <Panel className={styles.card}>
      <div className={`preview-empty-icon ${styles.icon} ${styles.dangerIcon}`}>
        <CircleAlert size={20} />
      </div>
      <h1 className={styles.title}>This view couldn’t be loaded</h1>
      <p className={`page-subtitle ${styles.copy}`}>
        Check that the policy API is available, then try again.
      </p>
      <Button onClick={reset}>
        <RotateCcw size={14} /> Try again
      </Button>
    </Panel>
  );
}
