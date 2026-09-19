"use client";

import { ArrowUpRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import styles from "../../landing.module.css";

const links = [
  { href: "#platform", label: "Platform" },
  { href: "#workflow", label: "How it works" },
  { href: "#explainability", label: "Explainability" },
  { href: "#governance", label: "Governance" },
];

export function MobileNavigation() {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const firstLinkRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    firstLinkRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function close() {
    setOpen(false);
  }

  return (
    <div className={styles.mobileNavigation}>
      <button
        ref={triggerRef}
        className={styles.menuButton}
        type="button"
        aria-expanded={open}
        aria-controls="mobile-navigation"
        aria-label={open ? "Close navigation" : "Open navigation"}
        onClick={() => setOpen((current) => !current)}
      >
        {open ? <X size={20} /> : <Menu size={20} />}
      </button>
      {open ? (
        <div className={styles.mobileMenu} id="mobile-navigation">
          <nav aria-label="Mobile navigation">
            {links.map((link, index) => (
              <a
                key={link.href}
                ref={index === 0 ? firstLinkRef : undefined}
                href={link.href}
                onClick={close}
              >
                <span>0{index + 1}</span>
                {link.label}
              </a>
            ))}
            <Link href="/learn" onClick={close}>
              <span>05</span>
              Learn
              <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          </nav>
          <div className={styles.mobileMenuActions}>
            <Link href="/login" onClick={close}>
              Sign in
            </Link>
            <Link href="/signup" onClick={close}>
              Get started <ArrowUpRight size={16} />
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
