"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bell, BookOpenCheck, CheckCircle2, Command, FilePlus2, LayoutDashboard, Menu, Network, Plus, ScrollText, Search, Settings, UserPlus, Users, X } from "lucide-react";
import { KeyboardEvent, useEffect, useState } from "react";

const navigation = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Employees", href: "/employees", icon: Users },
  { label: "Policies", href: "/policies", icon: BookOpenCheck },
  { label: "Groups", href: "/groups", icon: Network },
  { label: "Audit log", href: "/audit", icon: ScrollText },
];

const commands = [
  { label: "Go to overview", description: "Assignment health and recent changes", href: "/", keywords: "home dashboard", icon: LayoutDashboard },
  { label: "Find an employee", description: "Browse assignments and employment facts", href: "/employees", keywords: "people workers", icon: Users },
  { label: "Add an employee", description: "Preview policies during onboarding", href: "/employees/new", keywords: "onboard hire create", icon: UserPlus },
  { label: "Browse policies", description: "Rules, versions, priorities, and impact", href: "/policies", keywords: "rules assignments", icon: BookOpenCheck },
  { label: "Create a policy", description: "Build and preview a new assignment rule", href: "/policies/new", keywords: "new rule", icon: FilePlus2 },
  { label: "Manage groups", description: "Membership and inherited policies", href: "/groups", keywords: "collections teams", icon: Network },
  { label: "Inspect the audit log", description: "Search every recorded change", href: "/audit", keywords: "history events changes", icon: ScrollText },
  { label: "Configure assignment fields", description: "One-value and many-value categories", href: "/settings", keywords: "setup cardinality", icon: Settings },
];

const activity = [
  { title: "Policy reconciliation complete", detail: "Engineering Access updated 4 employees", time: "12m" },
  { title: "Employee profile changed", detail: "Jordan Lee moved to Product", time: "1h" },
  { title: "Override needs review", detail: "Devon Moore · Monthly pay schedule", time: "1d" },
];

export function AppShell({ children, connected }: { children: React.ReactNode; connected: boolean }) {
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const isActive = (href: string) => href === "/" ? pathname === href : pathname.startsWith(href);
  const currentPage = navigation.find((item) => isActive(item.href))?.label ?? (pathname.startsWith("/settings") ? "Assignment fields" : "PolicyOS");
  const filteredCommands = commands.filter((item) => `${item.label} ${item.description} ${item.keywords}`.toLowerCase().includes(query.toLowerCase()));

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

  return (
    <div className="app-layout">
      {menuOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar${menuOpen ? " open" : ""}`} aria-label="Workspace navigation">
        <div className="brand"><div className="brand-mark">P</div><div><div className="brand-title">PolicyOS</div><div className="brand-subtitle">Assignment engine</div></div><button className="sidebar-close" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={16} /></button></div>
        <div className="nav-label">Workspace</div>
        <nav className="nav-list" aria-label="Primary navigation">{navigation.map((item) => { const Icon = item.icon; return <Link className={`nav-item${isActive(item.href) ? " active" : ""}`} href={item.href} key={item.href} onClick={() => setMenuOpen(false)} aria-current={isActive(item.href) ? "page" : undefined}><Icon size={16} strokeWidth={1.8} />{item.label}</Link>; })}</nav>
        <div className="nav-label">Manage</div>
        <nav className="nav-list" aria-label="Settings navigation"><Link className={`nav-item${isActive("/settings") ? " active" : ""}`} href="/settings" onClick={() => setMenuOpen(false)} aria-current={isActive("/settings") ? "page" : undefined}><Settings size={16} strokeWidth={1.8} />Assignment fields</Link></nav>
        <button className="sidebar-command" onClick={() => { setCommandOpen(true); setMenuOpen(false); }}><Search size={14} /><span>Quick find</span><kbd>⌘K</kbd></button>
        <div className="sidebar-footer"><div className="company-switcher"><div className="company-avatar">AC</div><div><div className="company-name">Acme, Inc.</div><div className="company-role">Company admin</div></div></div></div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-context"><button className="icon-button mobile-menu-button" onClick={() => setMenuOpen((value) => !value)} aria-label={menuOpen ? "Close navigation" : "Open navigation"}>{menuOpen ? <X size={17} /> : <Menu size={17} />}</button><span className="topbar-page">{currentPage}</span><span className="topbar-divider" /><span className="system-dot" data-connected={connected} /><span className="system-copy">{connected ? "Engine current" : "Demo mode"}</span></div>
          <div className="topbar-actions"><button className="command-trigger" onClick={() => { setCommandOpen(true); setActivityOpen(false); }}><Search size={14} /><span>Search or jump to…</span><kbd><Command size={10} />K</kbd></button><div className="activity-wrap"><button className="icon-button" aria-label="Open activity center" aria-expanded={activityOpen} onClick={() => { setActivityOpen((current) => !current); setCommandOpen(false); }}><Bell size={16} strokeWidth={1.8} /><span className="notification-dot" /></button>{activityOpen && <div className="activity-popover"><div className="popover-head"><div><strong>Activity</strong><span>What changed recently</span></div><span className="badge accent">3 new</span></div><div className="popover-list">{activity.map((item) => <div className="popover-item" key={item.title}><span className="activity-icon"><CheckCircle2 size={13} /></span><span><strong>{item.title}</strong><small>{item.detail}</small></span><time>{item.time}</time></div>)}</div><Link className="popover-footer" href="/audit" onClick={() => setActivityOpen(false)}>View complete audit log</Link></div>}</div></div>
        </header>
        <main className="content" id="main-content">{children}</main>
      </div>
      {commandOpen && <div className="command-backdrop" role="presentation" onMouseDown={() => setCommandOpen(false)}><section className="command-menu" role="dialog" aria-modal="true" aria-label="Quick find" onMouseDown={(event) => event.stopPropagation()}><div className="command-input"><Search size={17} /><input autoFocus value={query} onChange={(event) => { setQuery(event.target.value); setActiveIndex(0); }} onKeyDown={onCommandKeyDown} placeholder="Search pages and actions…" aria-label="Search pages and actions" /><kbd>Esc</kbd></div><div className="command-results" role="listbox">{filteredCommands.map((item, index) => { const Icon = item.icon; return <button className={`command-item${index === activeIndex ? " active" : ""}`} onMouseEnter={() => setActiveIndex(index)} onClick={() => runCommand(item.href)} role="option" aria-selected={index === activeIndex} key={item.href + item.label}><span className="command-icon"><Icon size={16} /></span><span><strong>{item.label}</strong><small>{item.description}</small></span>{item.href.includes("new") && <Plus size={13} />}</button>; })}{filteredCommands.length === 0 && <div className="command-empty">No matching page or action.</div>}</div><div className="command-footer"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span></div></section></div>}
    </div>
  );
}
