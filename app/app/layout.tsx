import type { Metadata } from "next";
import "./globals.css";
import { AmbientVibes } from "@/components/ambient-vibes";

export const metadata: Metadata = {
  title: "climb-ramp",
  description: "speed-ramp climbing videos",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen relative">
        <AmbientVibes />
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
