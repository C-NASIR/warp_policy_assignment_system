import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { RootProvider } from "fumadocs-ui/provider/next";
import { AppShell, WebMcpTools } from "@/components/shell";
import { getAccountSecurity, getBackendStatus, getCurrentUser } from "@/lib/backend";
import { getLearnSearchEntries } from "@/lib/learn-source";
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
    images: [
      { url: "/og.png", width: 1200, height: 630, alt: "PolicyOS policy assignment system" },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "PolicyOS",
    description: "Every employee policy assignment, resolved and explained.",
    images: ["/og.png"],
  },
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const [backendStatus, currentUser] = await Promise.all([
    getBackendStatus().catch(() => null),
    getCurrentUser().catch(() => null),
  ]);
  const accountSecurity = currentUser ? await getAccountSecurity().catch(() => null) : null;
  const learnSearchEntries = getLearnSearchEntries();
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <body>
        <RootProvider search={{ enabled: false }} theme={{ enabled: false }}>
          <WebMcpTools />
          <AppShell
            backendReady={backendStatus?.status === "ok" && backendStatus.database === "ready"}
            currentUser={currentUser}
            securityEvents={accountSecurity?.events ?? []}
            learnSearchEntries={learnSearchEntries}
          >
            {children}
          </AppShell>
        </RootProvider>
      </body>
    </html>
  );
}
