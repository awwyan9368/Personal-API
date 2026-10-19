import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./features/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg-primary)",
        surface: "var(--bg-surface)",
        card: "var(--bg-card)",
        panel: "var(--bg-panel)",
        border: "var(--border-subtle)",
        foreground: "var(--text-primary)",
        muted: "var(--text-muted)",
        accent: {
          violet: "#8b5cf6",
          blue: "#3b82f6",
          lime: "#84cc16",
          amber: "#f59e0b",
          danger: "#ef4444",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Inter",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "Consolas",
          "Monaco",
          "monospace",
        ],
      },
    },
  },
  plugins: [],
};

export default config;

