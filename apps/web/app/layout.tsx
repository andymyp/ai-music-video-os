import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// Self-hosted at build time; the CSS defines a system fallback stack, so the
// UI degrades gracefully if the font fetch is ever unavailable.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "AI Music Video OS",
    template: "%s · AI Music Video OS",
  },
  description:
    "Local-first AI instrumental music video production — generate a 16:9 long-form and 9:16 short-form content package from one action.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#09090b", // zinc-950
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-dvh bg-zinc-950 text-zinc-100 antialiased">
        {children}
      </body>
    </html>
  );
}
