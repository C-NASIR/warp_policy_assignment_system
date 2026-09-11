import Link from "next/link";

export function PaginationControls({
  path,
  params,
  total,
  limit,
  offset,
  itemLabel,
}: {
  path: string;
  params: Record<string, string | undefined>;
  total: number;
  limit: number;
  offset: number;
  itemLabel: string;
}) {
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + limit, total);
  const previousOffset = Math.max(0, offset - limit);
  const nextOffset = offset + limit;

  function href(next: number) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value) query.set(key, value);
    }
    if (next > 0) query.set("offset", String(next));
    const suffix = query.toString();
    return suffix ? `${path}?${suffix}` : path;
  }

  return (
    <div className="pagination-footer">
      <span>
        Showing {first}–{last} of {total} {itemLabel}
      </span>
      <span className="heading-actions">
        {offset > 0 ? (
          <Link className="text-button" href={href(previousOffset)}>
            Previous
          </Link>
        ) : (
          <span className="text-button" aria-disabled="true">
            Previous
          </span>
        )}
        {nextOffset < total ? (
          <Link className="text-button" href={href(nextOffset)}>
            Next
          </Link>
        ) : (
          <span className="text-button" aria-disabled="true">
            Next
          </span>
        )}
      </span>
    </div>
  );
}
