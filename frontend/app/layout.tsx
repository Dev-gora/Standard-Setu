import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Standard Setu — AI Standards Engine for Procurement",
  description:
    "AI-powered recommendation engine for Indian Standards (SIH26108). Describe what you're procuring and get the standard to cite, the latest edition, allied standards, and mandatory certification checks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen antialiased transition-colors duration-300" style={{ background: 'var(--background)', color: 'var(--foreground)' }}>{children}</body>
    </html>
  );
}
