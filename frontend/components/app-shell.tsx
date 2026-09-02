"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bell, BookOpenCheck, LayoutDashboard, Menu, Network, ScrollText, Settings, Users, X } from "lucide-react";
import { useState } from "react";

const navigation = [
  { label: "Overview", href: "/", icon: LayoutDashboard },
  { label: "Employees", href: "/employees", icon: Users },
  { label: "Policies", href: "/policies", icon: BookOpenCheck },
  { label: "Groups", href: "/groups", icon: Network },
  { label: "Audit log", href: "/audit", icon: ScrollText },
];

export function AppShell({ children, connected }: { children: React.ReactNode; connected: boolean }) {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const isActive = (href: string) => href === "/" ? pathname === href : pathname.startsWith(href);

  return (
    <div className="app-layout">
      <aside className={`sidebar${menuOpen ? " open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">P</div>
          <div><div className="brand-title">PolicyOS</div><div className="brand-subtitle">Assignment engine</div></div>
        </div>
        <div className="nav-label">Workspace</div>
        <nav className="nav-list" aria-label="Primary navigation">
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <Link className={`nav-item${isActive(item.href) ? " active" : ""}`} href={item.href} key={item.href} onClick={() => setMenuOpen(false)}>
                <Icon size={16} strokeWidth={1.8} />{item.label}
              </Link>
            );
          })}
        </nav>
        <div className="nav-label">Manage</div>
        <nav className="nav-list" aria-label="Settings navigation">
          <Link className={`nav-item${isActive("/settings") ? " active" : ""}`} href="/settings" onClick={() => setMenuOpen(false)}>
            <Settings size={16} strokeWidth={1.8} />Assignment fields
          </Link>
        </nav>
        <div className="sidebar-footer">
          <div className="company-switcher">
            <div className="company-avatar">AC</div>
            <div><div className="company-name">Acme, Inc.</div><div className="company-role">Company admin</div></div>
          </div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-context">
            <button className="icon-button mobile-menu-button" onClick={() => setMenuOpen((value) => !value)} aria-label={menuOpen ? "Close navigation" : "Open navigation"}>
              {menuOpen ? <X size={17} /> : <Menu size={17} />}
            </button>
            <span className="system-dot" style={connected ? undefined : { background: "#d18a2e", boxShadow: "0 0 0 4px #f5e8d6" }} />{connected ? "Assignment engine is current" : "Demo workspace · connect API to persist"}
          </div>
          <div className="topbar-actions"><button className="icon-button" aria-label="Notifications"><Bell size={16} strokeWidth={1.8} /></button></div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
