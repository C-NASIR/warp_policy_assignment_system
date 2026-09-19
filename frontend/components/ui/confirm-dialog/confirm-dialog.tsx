"use client";

import { TriangleAlert, X } from "lucide-react";
import { Button } from "../button/button";
import { useModalAccessibility } from "@/lib/use-modal-accessibility";
import styles from "./confirm-dialog.module.css";

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busy = false,
  tone = "danger",
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  tone?: "danger" | "primary";
  onCancel(): void;
  onConfirm(): void;
}) {
  useModalAccessibility(open, onCancel);
  if (!open) return null;

  return (
    <div className={styles.backdrop} role="presentation" onMouseDown={onCancel}>
      <section
        className={styles.dialog}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirmation-title"
        aria-describedby="confirmation-description"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <button className={styles.close} onClick={onCancel} aria-label="Cancel and close">
          <X size={16} />
        </button>
        <span className={styles.icon} aria-hidden="true">
          <TriangleAlert size={18} />
        </span>
        <h2 id="confirmation-title">{title}</h2>
        <p id="confirmation-description">{description}</p>
        <div className={styles.actions}>
          <Button data-autofocus="true" variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </section>
    </div>
  );
}
