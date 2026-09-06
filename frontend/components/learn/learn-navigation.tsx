import Link from "next/link";
import { ArrowLeft, BookOpenCheck } from "lucide-react";
import { getLearnNavigation } from "@/lib/learn-source";

export function LearnNavigation({ currentUrl }: { currentUrl: string }) {
  const navigation = getLearnNavigation();
  const content = (
    <>
      {navigation.map((group) => (
        <section className="learn-nav-group" key={group.section}>
          <div className="learn-nav-label">{group.label}</div>
          <div className="learn-nav-links">
            {group.pages.map((page, index) => (
              <Link
                className={page.url === currentUrl ? "active" : undefined}
                href={page.url}
                aria-current={page.url === currentUrl ? "page" : undefined}
                key={page.url}
              >
                <span>{page.data.title}</span>
                <small>{String(index + 1).padStart(2, "0")}</small>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </>
  );

  return (
    <>
      <aside className="learn-sidebar" aria-label="Learning center navigation">
        <Link className="learn-app-link" href="/">
          <span className="learn-app-mark">P</span>
          <span><strong>PolicyOS</strong><small>Back to the app</small></span>
          <ArrowLeft size={15} aria-hidden="true" />
        </Link>
        <Link className="learn-sidebar-home" href="/learn">
          <span className="learn-sidebar-icon"><BookOpenCheck size={16} /></span>
          <span><strong>Learn PolicyOS</strong><small>Concepts, application, practice</small></span>
        </Link>
        <nav className="learn-sidebar-navigation" aria-label="Learning center articles">{content}</nav>
      </aside>
      <div className="learn-mobile-shell">
        <Link className="learn-mobile-app-link" href="/"><span className="learn-app-mark">P</span><span>PolicyOS</span><small>Back to app</small></Link>
        <details className="learn-mobile-navigation">
          <summary><BookOpenCheck size={17} /> Browse learning center</summary>
          <nav aria-label="Learning center navigation">{content}</nav>
        </details>
      </div>
    </>
  );
}
