import type { Metadata } from "next";
import { Permanent_Marker, Press_Start_2P, VT323 } from "next/font/google";
import "./globals.css";
import { AmbientVibes } from "@/components/ambient-vibes";
import { SoundFx } from "@/components/sound/sound-fx";

export const metadata: Metadata = {
  title: "SENDIT // Speed Ramp System",
  description:
    "Auto speed-ramp your climbing sends. 50% through the video = 50% up the boulder. MediaPipe pose detection + FFmpeg + retro VCR vibes.",
};

const pixelFont = Press_Start_2P({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-pixel",
});

const retroFont = VT323({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-retro",
});

const markerFont = Permanent_Marker({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-marker",
});

function RackScrew() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" className="opacity-40" aria-hidden="true">
      <circle cx="6" cy="6" r="5" fill="#333" stroke="#555" strokeWidth="0.5" />
      <line x1="3" y1="6" x2="9" y2="6" stroke="#222" strokeWidth="1.2" />
      <circle cx="6" cy="6" r="2" fill="none" stroke="#444" strokeWidth="0.3" />
    </svg>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${pixelFont.variable} ${retroFont.variable} ${markerFont.variable}`}>
      <body className="min-h-screen relative overflow-x-hidden">
        <AmbientVibes />
        <SoundFx />

        <div className="relative z-10 min-h-screen">
          {/* Rack-mount top rail */}
          <div
            className="w-full h-3 flex items-center justify-between px-3"
            style={{
              backgroundImage: "url('/retro/rack-panel.png')",
              backgroundSize: "256px",
              borderBottom: "1px solid #333",
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05), 0 2px 4px rgba(0,0,0,0.6)",
            }}
          >
            <RackScrew />
            <RackScrew />
            <RackScrew />
            <RackScrew />
          </div>

          {children}

          {/* Rack-mount bottom rail */}
          <div
            className="w-full h-3 flex items-center justify-between px-3"
            style={{
              backgroundImage: "url('/retro/rack-panel.png')",
              backgroundSize: "256px",
              borderTop: "1px solid #333",
              boxShadow: "inset 0 -1px 0 rgba(255,255,255,0.05), 0 -2px 4px rgba(0,0,0,0.6)",
            }}
          >
            <RackScrew />
            <RackScrew />
            <RackScrew />
            <RackScrew />
          </div>
        </div>
      </body>
    </html>
  );
}
