import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./lib/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        "bg-card": "var(--bg-card)",
        "bg-card-solid": "var(--bg-card-solid)",
        "bg-input": "var(--bg-input)",
        border: "var(--border)",
        text: "var(--text)",
        "text-muted": "var(--text-muted)",
        accent: "var(--accent)",
        "accent-light": "var(--accent-light)",
        "accent-hover": "var(--accent-hover)",
        warm: "var(--warm)",
        "warm-light": "var(--warm-light)",
        danger: "var(--danger)",
        "neon-cyan": "var(--neon-cyan)",
        "neon-magenta": "var(--neon-magenta)",
        "neon-lime": "var(--neon-lime)",
        "neon-orange": "var(--neon-orange)",
        chrome: "var(--chrome)",
        "chrome-dark": "var(--chrome-dark)",
        "chrome-light": "var(--chrome-light)",
        "panel-bg": "var(--panel-bg)",
      },
      fontFamily: {
        pixel: ["var(--font-pixel)", "monospace"],
        retro: ["var(--font-retro)", "'Courier New'", "monospace"],
      },
      boxShadow: {
        "glow-cyan": "0 0 8px rgba(0,229,255,0.4), 0 0 20px rgba(0,229,255,0.15)",
        "glow-magenta": "0 0 8px rgba(224,64,251,0.4), 0 0 20px rgba(224,64,251,0.15)",
        "glow-orange": "0 0 8px rgba(255,110,64,0.4), 0 0 20px rgba(255,110,64,0.15)",
        bevel: "inset 1px 1px 0 rgba(255,255,255,0.15), inset -1px -1px 0 rgba(0,0,0,0.3), 0 2px 8px rgba(0,0,0,0.4)",
      },
    },
  },
  plugins: [],
};
export default config;
