import { CalendarCheck2, Clock3, ShieldCheck, Users } from "lucide-react";
import type { LearnPage } from "@/lib/learn-source";

export function ArticleMeta({ page }: { page: LearnPage }) {
  if (page.data.status === "outline") {
    return page.slugs.length > 0 ? <div className="learn-article-meta"><span>Lesson placeholder</span></div> : null;
  }

  return (
    <div className="learn-article-meta" aria-label="Article information">
      <span><Clock3 size={13} /> {page.data.reading_time} min read</span>
      <span><Users size={13} /> {page.data.audiences.join(", ")}</span>
      <span><ShieldCheck size={13} /> {page.data.owner}</span>
      <span><CalendarCheck2 size={13} /> Verified {formatDate(page.data.last_verified)}</span>
    </div>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).format(new Date(`${value}T00:00:00Z`));
}
