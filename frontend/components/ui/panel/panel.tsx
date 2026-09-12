import type { HTMLAttributes, ReactNode } from "react";
import { classNames } from "@/lib/class-names";
import styles from "./panel.module.css";

export function Panel({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={classNames(styles.panel, className)} {...props} />;
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
