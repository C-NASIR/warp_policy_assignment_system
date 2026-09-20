"use client";

import { useRouter } from "next/navigation";
import { useOptimistic, useTransition } from "react";

export function useFilterNavigation<Filters>(filters: Filters) {
  const router = useRouter();
  const [optimisticFilters, setOptimisticFilters] = useOptimistic(filters);
  const [isPending, startTransition] = useTransition();

  function navigate(href: string, nextFilters: Filters) {
    startTransition(() => {
      setOptimisticFilters(nextFilters);
      router.push(href, { scroll: false });
    });
  }

  return { filters: optimisticFilters, isPending, navigate };
}
