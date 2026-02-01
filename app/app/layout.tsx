import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "climb-ramp",
  description: "speed-ramp climbing videos",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
