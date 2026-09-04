"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, BookOpenCheck, CheckCircle2, Command, FilePlus2, KeyRound, LayoutDashboard, LogOut, Menu, Network, Plus, ScrollText, Search, Settings, ShieldCheck, UserPlus, Users, X } from "lucide-react";
import { KeyboardEvent, useEffect, useState } from "react";
import { hasPermission } from "@/lib/permissions";
import type { CurrentUser, SecurityEvent } from "@/lib/types";

const navigation = [
  { label: "Overview", href: "/", icon: LayoutDashboard, permission: "*" },
  { label: "Employees", href: "/employees", icon: Users, permission: "employees:read" },
  { label: "Policies", href: "/policies", icon: BookOpenCheck, permission: "policies:read" },
  { label: "Approvals", href: "/approvals", icon: CheckCircle2, permission: "changes:approve" },
  { label: "Groups", href: "/groups", icon: Network, permission: "groups:read" },
  { label: "Audit log", href: "/audit", icon: ScrollText, permission: "audit:read" },
];

const commands = [
  { label: "Go to overview", description: "Assignment health and recent changes", href: "/", keywords: "home dashboard", icon: LayoutDashboard, permission: "*" },
  { label: "Find an employee", description: "Browse assignments and employment facts", href: "/employees", keywords: "people workers", icon: Users, permission: "employees:read" },
  { label: "Add an employee", description: "Preview policies during onboarding", href: "/employees/new", keywords: "onboard hire create", icon: UserPlus, permission: "employees:create" },
  { label: "Browse policies", description: "Rules, versions, priorities, and impact", href: "/policies", keywords: "rules assignments", icon: BookOpenCheck, permission: "policies:read" },
  { label: "Create a policy", description: "Build and preview a new assignment rule", href: "/policies/new", keywords: "new rule", icon: FilePlus2, permission: "policies:create" },
  { label: "Review approvals", description: "Approve and execute sensitive changes", href: "/approvals", keywords: "review requests changes", icon: CheckCircle2, permission: "changes:approve" },
  { label: "Manage groups", description: "Membership and inherited policies", href: "/groups", keywords: "collections teams", icon: Network, permission: "groups:read" },
  { label: "Inspect the audit log", description: "Search every recorded change", href: "/audit", keywords: "history events changes", icon: ScrollText, permission: "audit:read" },
  { label: "Configure assignment fields", description: "One-value and many-value categories", href: "/settings", keywords: "setup cardinality", icon: Settings, permission: "settings:read" },
  { label: "Manage access", description: "Users, roles, and permissions", href: "/access", keywords: "authorization accounts", icon: ShieldCheck, permission: "access:read" },
  { label: "Review privileged access", description: "MFA, stale users, and broad roles", href: "/access/review", keywords: "security permissions report", icon: ShieldCheck, permission: "access:review" },
];

const activity = [
  { title: "Policy reconciliation complete", detail: "Engineering Access updated 4 employees", time: "12m" },
  { title: "Employee profile changed", detail: "Jordan Lee moved to Product", time: "1h" },
  { title: "Override needs review", detail: "Devon Moore · Monthly pay schedule", time: "1d" },
];

export function AppShell({ children, connected, currentUser, securityEvents }: { children: React.ReactNode; connected: boolean; currentUser: CurrentUser | null; securityEvents: SecurityEvent[] }) {
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [loggingOut, setLoggingOut] = useState(false);
  const visibleActivity = connected ? securityEvents.filter((item) => item.severity !== "info" && !item.acknowledged_at).slice(0, 5).map((item) => ({ title: item.event_type.replaceAll("_", " "), detail: String(item.details.ip ?? "Account security event"), time: item.created_at.slice(0, 10) })) : activity;
  const isAuthPage = pathname === "/login" || pathname === "/setup" || pathname === "/recover";
  const isActive = (href: string) => href === "/" ? pathname === href : pathname.startsWith(href);
  const currentPage = navigation.find((item) => isActive(item.href))?.label ?? (pathname.startsWith("/settings") ? "Assignment fields" : pathname.startsWith("/access") ? "Access control" : pathname.startsWith("/account") ? "Account security" : "PolicyOS");
  const visibleNavigation = navigation.filter((item) => !connected || hasPermission(currentUser, item.permission));
  const filteredCommands = commands.filter((item) => (!connected || hasPermission(currentUser, item.permission)) && `${item.label} ${item.description} ${item.keywords}`.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault(); setCommandOpen((current) => !current); setActivityOpen(false);
      }
      if (event.key === "Escape") { setCommandOpen(false); setActivityOpen(false); setMenuOpen(false); }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!commandOpen && !menuOpen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [commandOpen, menuOpen]);

  function runCommand(href: string) {
    setCommandOpen(false); setQuery(""); setActiveIndex(0); router.push(href);
  }

  function onCommandKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") { event.preventDefault(); setActiveIndex((current) => Math.min(current + 1, Math.max(0, filteredCommands.length - 1))); }
    if (event.key === "ArrowUp") { event.preventDefault(); setActiveIndex((current) => Math.max(current - 1, 0)); }
    if (event.key === "Enter" && filteredCommands[activeIndex]) { event.preventDefault(); runCommand(filteredCommands[activeIndex].href); }
  }

  async function logout() {
    setLoggingOut(true);
    try {
      await fetch("/api/backend/auth/logout", { method: "POST" });
    } finally {
      router.replace("/login");
      router.refresh();
      setLoggingOut(false);
    }
  }

  if (isAuthPage) return <>{children}</>;

  return (
    <div className="app-layout">
      {menuOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar${menuOpen ? " open" : ""}`} aria-label="Workspace navigation">
        <div className="brand"><div className="brand-mark">P</div><div><div className="brand-title">PolicyOS</div><div className="brand-subtitle">Assignment engine</div></div><button className="sidebar-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={16} /></button></div>
        <div className="nav-label">Workspace</div>
        <nav className="nav-list" aria-label="Primary navigation">{visibleNavigation.map((item) => { const Icon = item.icon; return <Link className={`nav-item${isActive(item.href) ? " active" : ""}`} href={item.href} key={item.href} onClick={() => setMenuOpen(false)} aria-current={isActive(item.href) ? "page" : undefined}><Icon size={16} strokeWidth={1.8} />{item.label}</Link>; })}</nav>
        <div className="nav-label">Manage</div>
        <nav className="nav-list" aria-label="Settings navigation">{(!connected || hasPermission(currentUser, "settings:read")) && <Link className={`nav-item${isActive("/settings") ? " active" : ""}`} href="/settings" onClick={() => setMenuOpen(false)} aria-current={isActive("/settings") ? "page" : undefined}><Settings size={16} strokeWidth={1.8} />Assignment fields</Link>}{currentUser && hasPermission(currentUser, "access:read") && <Link className={`nav-item${pathname === "/access" ? " active" : ""}`} href="/access" onClick={() => setMenuOpen(false)} aria-current={pathname === "/access" ? "page" : undefined}><ShieldCheck size={16} strokeWidth={1.8} />Access control</Link>}{currentUser && hasPermission(currentUser, "access:review") && <Link className={`nav-item${isActive("/access/review") ? " active" : ""}`} href="/access/review" onClick={() => setMenuOpen(false)} aria-current={isActive("/access/review") ? "page" : undefined}><ShieldCheck size={16} strokeWidth={1.8} />Access review</Link>}{currentUser && <Link className={`nav-item${isActive("/account") ? " active" : ""}`} href="/account/security" onClick={() => setMenuOpen(false)} aria-current={isActive("/account") ? "page" : undefined}><KeyRound size={16} strokeWidth={1.8} />Account security</Link>}</nav>
        <button className="sidebar-command" onClick={() => { setCommandOpen(true); setMenuOpen(false); }}><Search size={14} /><span>Quick find</span><kbd>⌘K</kbd></button>
        <div className="sidebar-footer">{currentUser ? <div className="account-summary"><div className="account-avatar">{currentUser.name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase()}</div><div className="account-copy"><div className="company-name">{currentUser.name}</div><div className="company-role">{currentUser.is_root ? "Root account" : currentUser.roles.map((role) => role.name).join(", ") || "No role"}</div></div><button className="account-logout" type="button" onClick={logout} disabled={loggingOut} aria-label="Sign out"><LogOut size={15} /></button></div> : <div className="company-switcher"><div className="company-avatar">AC</div><div><div className="company-name">Acme, Inc.</div><div className="company-role">Demo workspace</div></div></div>}</div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-context"><button className="icon-button mobile-menu-button" onClick={() => setMenuOpen((value) => !value)} aria-label={menuOpen ? "Close navigation" : "Open navigation"}>{menuOpen ? <X size={17} /> : <Menu size={17} />}</button><span className="topbar-page">{currentPage}</span><span className="topbar-divider" /><span className="system-dot" data-connected={connected} /><span className="system-copy">{connected ? "Engine current" : "Demo mode"}</span></div>
          <div className="topbar-actions"><button className="command-trigger" onClick={() => { setCommandOpen(true); setActivityOpen(false); }}><Search size={14} /><span>Search or jump to…</span><kbd><Command size={10} />K</kbd></button>{currentUser && <div className="activity-wrap"><button className="icon-button" aria-label="Open security notifications" aria-expanded={activityOpen} onClick={() => { setActivityOpen((current) => !current); setCommandOpen(false); }}><Bell size={16} strokeWidth={1.8} />{visibleActivity.length > 0 && <span className="notification-dot" />}</button>{activityOpen && <div className="activity-popover"><div className="popover-head"><div><strong>Security</strong><span>Account alerts requiring review</span></div><span className="badge accent">{visibleActivity.length} new</span></div><div className="popover-list">{visibleActivity.length === 0 && <div className="command-empty">No unreviewed security alerts.</div>}{visibleActivity.map((item) => <div className="popover-item" key={`${item.title}-${item.time}`}><span className="activity-icon"><CheckCircle2 size={13} /></span><span><strong>{item.title}</strong><small>{item.detail}</small></span><time>{item.time}</time></div>)}</div><Link className="popover-footer" href="/account/security" onClick={() => setActivityOpen(false)}>Review security events</Link></div>}</div>}</div>
        </header>
        <main className="content" id="main-content">{children}</main>
      </div>
      {commandOpen && <div className="command-backdrop" role="presentation" onMouseDown={() => setCommandOpen(false)}><section className="command-menu" role="dialog" aria-modal="true" aria-label="Quick find" onMouseDown={(event) => event.stopPropagation()}><div className="command-input"><Search size={17} /><input autoFocus value={query} onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); }} onKeyDown={onCommandKeyDown} placeholder="Search pages and actions…" aria-label="Search pages and actions" /><kbd>Esc</kbd></div><div className="command-results" role="listbox">{filteredCommands.map((item, index) => { const Icon = item.icon; return <button className={`command-item${index === activeIndex ? " active" : ""}`} onMouseEnter={() => setActiveIndex(index)} onClick={() => runCommand(item.href)} role="option" aria-selected={index === activeIndex} key={item.href + item.label}><span className="command-icon"><Icon size={16} /></span><span><strong>{item.label}</strong><small>{item.description}</small></span>{item.href.includes("new") && <Plus size={13} />}</button>; })}{filteredCommands.length === 0 && <div className="command-empty">No matching page or action.</div>}</div><div className="command-footer"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span></div></section></div>}
    </div>
  );
}
