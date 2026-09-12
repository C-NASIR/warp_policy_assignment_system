import type { HTMLAttributes, ReactNode } from "react";
import { classNames } from "@/lib/class-names";
import styles from "./panel.module.css";

type PanelElement = "article" | "div" | "section";

export function Panel({
  as: Component = "section",
  className,
  clipped = false,
  ...props
}: HTMLAttributes<HTMLElement> & { as?: PanelElement; clipped?: boolean }) {
  return (
    <Component
      className={classNames(styles.panel, clipped && styles.clipped, className)}
      {...props}
    />
  );
}

export function PanelHeader({
  action,
  caption,
  className,
  title,
  ...props
}: Omit<HTMLAttributes<HTMLDivElement>, "title"> & {
  action?: ReactNode;
  caption?: ReactNode;
  title: ReactNode;
}) {
  return (
    <div className={classNames(styles.header, className)} {...props}>
      <div className={styles.heading}>
        <h2 className={styles.title}>{title}</h2>
        {caption ? <p className={styles.caption}>{caption}</p> : null}
      </div>
      {action}
    </div>
  );
}

export function PanelBody({
  className,
  flush = false,
  ...props
}: HTMLAttributes<HTMLDivElement> & { flush?: boolean }) {
  return <div className={classNames(styles.body, flush && styles.flush, className)} {...props} />;
}
