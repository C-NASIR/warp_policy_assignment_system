import type { HTMLAttributes, TableHTMLAttributes } from "react";
import { classNames } from "@/lib/class-names";
import styles from "./data-table.module.css";

export function DataTable({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={classNames(styles.table, className)} {...props} />;
}

export function TablePanel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={classNames(styles.panel, className)} {...props} />;
}

export function TableScroll({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={classNames(styles.scroll, className)} {...props} />;
}
