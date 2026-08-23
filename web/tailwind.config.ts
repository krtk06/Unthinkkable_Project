import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#121210",
        surface: "rgba(30, 30, 28, 0.6)",
        "surface-hover": "rgba(40, 40, 36, 0.7)",
        border: "rgba(255, 255, 255, 0.08)",
        "border-hover": "rgba(255, 255, 255, 0.12)",
        text: {
          DEFAULT: "#e8e6e1",
          secondary: "#9a9890",
        },
        accent: {
          DEFAULT: "#34d399",
          hover: "#6ee7b7",
        },
        error: "#f87171",
        warning: "#fbbf24",
        success: "#34d399",
        band: {
          absent: "#f87171",
          limited: "#fb923c",
          partial: "#fbbf24",
          strong: "#34d399",
          exceptional: "#10b981",
        },
      },
      borderRadius: {
        glass: "12px",
      },
      backdropBlur: {
        glass: "16px",
      },
      fontFamily: {
        ui: ["var(--font-inter)", "system-ui", "sans-serif"],
        data: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
