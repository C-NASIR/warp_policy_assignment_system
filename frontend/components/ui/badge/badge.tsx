import type { HTMLAttributes } from "react";
import { classNames } from "@/lib/class-names";
import styles from "./badge.module.css";

export type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger";

export function Badge({
  className,
  tone = "neutral",
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return <span className={classNames(styles.badge, styles[tone], className)} {...props} />;
}
