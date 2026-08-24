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
        bg: "#0b0d10",
        surface: "rgba(20, 22, 26, 0.7)",
        "surface-hover": "rgba(30, 33, 38, 0.85)",
        border: "rgba(255, 255, 255, 0.08)",
        "border-hover": "rgba(255, 255, 255, 0.14)",
        text: {
          DEFAULT: "#e8e6e1",
          secondary: "#9a9890",
        },
        accent: {
          DEFAULT: "#5d5d65",
          hover: "#7a7a85",
        },
        error: "#f87171",
        warning: "#fbbf24",
        success: "#5d5d65",
        band: {
          absent: "#f87171",
          limited: "#fb923c",
          partial: "#fbbf24",
          strong: "#5d5d65",
          exceptional: "#5d5d65",
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
