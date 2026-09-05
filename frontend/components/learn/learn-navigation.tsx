import Link from "next/link";
import { BookOpenCheck } from "lucide-react";
import { getLearnNavigation } from "@/lib/learn-source";

export function LearnNavigation({ currentUrl }: { currentUrl: string }) {
  const navigation = getLearnNavigation();
  const content = (
    <>
      {navigation.map((group) => (
        <section className="learn-nav-group" key={group.section}>
          <div className="learn-nav-label">{group.label}</div>
          <div className="learn-nav-links">
            {group.pages.map((page) => (
              <Link
                className={page.url === currentUrl ? "active" : undefined}
                href={page.url}
                aria-current={page.url === currentUrl ? "page" : undefined}
                key={page.url}
              >
                <span>{page.data.title}</span>
                <small>{page.data.reading_time} min</small>
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
        <Link className="learn-sidebar-home" href="/learn">
          <span className="learn-sidebar-icon"><BookOpenCheck size={16} /></span>
          <span><strong>Learn PolicyOS</strong><small>Courses and answers</small></span>
        </Link>
        {content}
      </aside>
      <details className="learn-mobile-navigation">
        <summary><BookOpenCheck size={15} /> Browse learning center</summary>
        <nav aria-label="Learning center navigation">{content}</nav>
      </details>
    </>
  );
}
