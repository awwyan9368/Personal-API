import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/AppShell";

export const metadata: Metadata = {
  title: "Personal Life OS — Local-First Life Analytics & Personal API",
  description:
    "Private, local-first personal operating system for habits, finance, screen time, focus, goals, wellbeing, knowledge graph, and personal REST API.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground font-sans antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

