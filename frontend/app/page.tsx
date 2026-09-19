import type { Metadata } from "next";
import { LandingPage } from "./_components/landing/landing-page";

export const metadata: Metadata = {
  title: { absolute: "PolicyOS — Workforce policy assignments, resolved and explained" },
  description:
    "Turn employee facts and organizational context into governed assignments. Preview impact, resolve overlap by priority, and explain every outcome.",
  openGraph: {
    title: "PolicyOS — Workforce policy assignments, resolved and explained",
    description:
      "Turn employee facts and organizational context into governed assignments—with previews, explicit priority, and a durable decision trail.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "PolicyOS — Workforce policy assignments, resolved and explained",
    description:
      "Turn employee facts and organizational context into governed assignments—with previews, explicit priority, and a durable decision trail.",
  },
};

export default function Home() {
  return <LandingPage />;
}
