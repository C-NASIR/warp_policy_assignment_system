import Link, { type LinkProps } from "next/link";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";
import { classNames } from "@/lib/class-names";
import styles from "./button.module.css";

export type ButtonVariant = "primary" | "secondary" | "danger";
export type ButtonSize = "default" | "small";

type SharedProps = {
  children: ReactNode;
  className?: string;
  fullWidth?: boolean;
  size?: ButtonSize;
  variant?: ButtonVariant;
};

function buttonClassName({
  className,
  fullWidth,
  size = "default",
  variant = "primary",
}: Omit<SharedProps, "children">) {
  return classNames(
    styles.button,
    variant !== "primary" && styles[variant],
    size === "small" && styles.small,
    fullWidth && styles.fullWidth,
    className,
  );
}

export function Button({
  children,
  className,
  fullWidth,
  size,
  variant,
  type = "button",
  ...props
}: SharedProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={buttonClassName({ className, fullWidth, size, variant })}
      type={type}
      {...props}
    >
      {children}
    </button>
  );
}

export function ButtonLink({
  children,
  className,
  fullWidth,
  size,
  variant,
  ...props
}: SharedProps & LinkProps & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof LinkProps>) {
  return (
    <Link className={buttonClassName({ className, fullWidth, size, variant })} {...props}>
      {children}
    </Link>
  );
}
