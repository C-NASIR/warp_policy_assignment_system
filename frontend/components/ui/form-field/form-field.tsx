import {
  forwardRef,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";
import { classNames } from "@/lib/class-names";
import styles from "./form-field.module.css";

export function FormField({
  children,
  className,
  error,
  full = false,
  hint,
  htmlFor,
  label,
  required = false,
}: {
  children: ReactNode;
  className?: string;
  error?: ReactNode;
  full?: boolean;
  hint?: ReactNode;
  htmlFor?: string;
  label: ReactNode;
  required?: boolean;
}) {
  return (
    <div className={classNames(styles.field, full && styles.full, className)}>
      <label className={styles.label} htmlFor={htmlFor}>
        {label}
        {required ? (
          <span className={styles.required} aria-hidden="true">
            *
          </span>
        ) : null}
      </label>
      {children}
      {error ? <p className={styles.error}>{error}</p> : null}
      {!error && hint ? <p className={styles.hint}>{hint}</p> : null}
    </div>
  );
}

export const TextInput = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function TextInput({ className, ...props }, ref) {
    return <input ref={ref} className={classNames(styles.control, className)} {...props} />;
  },
);

export const SelectInput = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  function SelectInput({ className, ...props }, ref) {
    return (
      <select
        ref={ref}
        className={classNames(styles.control, styles.select, className)}
        {...props}
      />
    );
  },
);
