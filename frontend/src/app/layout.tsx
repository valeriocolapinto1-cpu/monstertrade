import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";

import { AppShell } from "@/components/app-shell";
import { ServiceWorker } from "@/components/service-worker";

import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "MonsterTrade", template: "%s · MonsterTrade" },
  description: "Analisi tecnica e sentiment per uso personale. Strumento informativo, non consulenza.",
  robots: { index: false, follow: false },
  appleWebApp: { capable: true, title: "MonsterTrade", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#0a0d13",
  colorScheme: "dark",
  viewportFit: "cover",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="it" className={`${inter.variable} dark h-full antialiased`}>
      <body className="min-h-full">
        <AppShell>{children}</AppShell>
        <ServiceWorker />
      </body>
    </html>
  );
}
