import type { Metadata } from "next";
import { LandingPage } from "./_components/landing/landing-page";

export const metadata: Metadata = {
  title: "PolicyOS — Explainable workforce policy assignments",
  description:
    "Define date-effective workforce policies, preview their impact, reconcile every change, and explain each assignment—from employee facts to the winning policy.",
};

export default function Home() {
  return <LandingPage />;
}
