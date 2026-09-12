import type { TableHTMLAttributes } from "react";
import { classNames } from "@/lib/class-names";
import styles from "./data-table.module.css";

export function DataTable({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={classNames(styles.table, className)} {...props} />;
}
