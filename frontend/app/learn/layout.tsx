import type { Metadata } from "next";
import "./learn.css";

export const metadata: Metadata = {
  title: { default: "Learn PolicyOS", template: "%s · Learn PolicyOS" },
  description: "Learn how PolicyOS turns workforce facts and policies into explainable assignments.",
};

export default function LearnLayout({ children }: LayoutProps<"/learn">) {
  return <div className="learn-route">{children}</div>;
}
