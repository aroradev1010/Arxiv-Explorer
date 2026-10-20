import type { Metadata } from "next";
import { Suspense } from "react";
import { Providers } from "@/components/layout/providers";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "ArXiv Explorer · Research, connected",
    template: "%s · ArXiv Explorer",
  },
  description:
    "Search academic research with keyword, semantic and hybrid retrieval.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <Providers>
          <a className="skip-link" href="#main">
            Skip to content
          </a>
          <Header />
          <main id="main" className="container">
            <Suspense fallback={<p role="status">Loading…</p>}>
              {children}
            </Suspense>
          </main>
          <Footer />
        </Providers>
      </body>
    </html>
  );
}
