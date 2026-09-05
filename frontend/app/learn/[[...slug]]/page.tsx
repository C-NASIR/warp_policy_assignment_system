import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ListTree } from "lucide-react";
import { notFound } from "next/navigation";
import { ArticleMeta } from "@/components/learn/article-meta";
import { LearnNavigation } from "@/components/learn/learn-navigation";
import { getLearnMdxComponents } from "@/components/learn/mdx-components";
import { getCurrentUser } from "@/lib/backend";
import { getOrderedLearnPages, labelForLearnSection, learnSource } from "@/lib/learn-source";

export function generateStaticParams() {
  return learnSource.generateParams();
}

export async function generateMetadata({ params }: PageProps<"/learn/[[...slug]]">): Promise<Metadata> {
  const { slug } = await params;
  const page = learnSource.getPage(slug);
  if (!page) return {};
  return { title: page.data.title, description: page.data.description };
}

export default async function LearnPage({ params }: PageProps<"/learn/[[...slug]]">) {
  const { slug } = await params;
  const page = learnSource.getPage(slug);
  if (!page || page.data.status === "retired") notFound();

  const currentUser = await getCurrentUser();
  const Body = page.data.body;
  const orderedPages = getOrderedLearnPages();
  const pageIndex = orderedPages.findIndex((item) => item.url === page.url);
  const previous = pageIndex > 0 ? orderedPages[pageIndex - 1] : null;
  const next = pageIndex >= 0 && pageIndex < orderedPages.length - 1 ? orderedPages[pageIndex + 1] : null;
  const isHome = page.slugs.length === 0;

  return (
    <div className="learn-layout">
      <LearnNavigation currentUrl={page.url} />
      <article className="learn-article-column">
        <header className="learn-article-header">
          <p className="eyebrow">{isHome ? "Learning center" : labelForLearnSection(page.data.section)}</p>
          <h1>{page.data.title}</h1>
          {page.data.description && <p className="learn-description">{page.data.description}</p>}
          <ArticleMeta page={page} />
          {page.data.prerequisites.length > 0 && <p className="learn-prerequisites"><strong>Before you start:</strong> {page.data.prerequisites.join(" · ")}</p>}
        </header>
        {page.data.toc.length > 0 && <details className="learn-mobile-toc"><summary><ListTree size={14} /> On this page</summary><TocList items={page.data.toc} /></details>}
        <div className="learn-body prose"><Body components={getLearnMdxComponents(currentUser)} /></div>
        {!isHome && <nav className="learn-pagination" aria-label="Lesson navigation">
          {previous ? <Link href={previous.url}><ArrowLeft size={15} /><span><small>Previous</small><strong>{previous.data.title}</strong></span></Link> : <span />}
          {next ? <Link className="next" href={next.url}><span><small>Next</small><strong>{next.data.title}</strong></span><ArrowRight size={15} /></Link> : <span />}
        </nav>}
      </article>
      <aside className="learn-toc" aria-label="On this page">
        <div><strong>On this page</strong>{page.data.toc.length ? <TocList items={page.data.toc} /> : <p>This overview has no subsections.</p>}</div>
      </aside>
    </div>
  );
}

function TocList({ items }: { items: { url: string; title: React.ReactNode; depth: number }[] }) {
  return <ol>{items.map((item) => <li style={{ paddingLeft: `${Math.max(0, item.depth - 2) * 12}px` }} key={item.url}><a href={item.url}>{item.title}</a></li>)}</ol>;
}
