import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AppShell } from "@/components/app-shell";
import { WebMcpTools } from "@/components/webmcp-tools";
import { apiConfigured, getAccountSecurity, getCurrentUser } from "@/lib/backend";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: { default: "PolicyOS", template: "%s · PolicyOS" },
  description: "Define, resolve, and explain every employee policy assignment from one place.",
  openGraph: {
    title: "PolicyOS",
    description: "Every employee policy assignment, resolved and explained.",
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "PolicyOS policy assignment system" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "PolicyOS",
    description: "Every employee policy assignment, resolved and explained.",
    images: ["/og.png"],
  },
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const currentUser = apiConfigured ? await getCurrentUser() : null;
  const accountSecurity = currentUser ? await getAccountSecurity() : null;
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body><WebMcpTools /><AppShell connected={apiConfigured} currentUser={currentUser} securityEvents={accountSecurity?.events ?? []}>{children}</AppShell></body>
    </html>
  );
}
