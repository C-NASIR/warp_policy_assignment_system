"use client";

import { useEffect } from "react";

export function KeepActiveLessonVisible({ currentUrl }: { currentUrl: string }) {
  useEffect(() => {
    const navigation = document.querySelector<HTMLElement>(".learn-sidebar-navigation");
    const activeLink = navigation?.querySelector<HTMLElement>('a[aria-current="page"]');
    if (!navigation || !activeLink) return;

    const navigationRect = navigation.getBoundingClientRect();
    const activeRect = activeLink.getBoundingClientRect();
    const edgePadding = 12;
    const isVisible =
      activeRect.top >= navigationRect.top + edgePadding &&
      activeRect.bottom <= navigationRect.bottom - edgePadding;

    if (isVisible) return;

    const centeredTop =
      navigation.scrollTop +
      activeRect.top -
      navigationRect.top -
      (navigation.clientHeight - activeRect.height) / 2;

    navigation.scrollTo({ top: Math.max(0, centeredTop), behavior: "auto" });
  }, [currentUrl]);

  return null;
}
